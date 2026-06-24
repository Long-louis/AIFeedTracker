# -*- coding: utf-8 -*-
"""
B 站 API 全局限流器（档位 C）

提供令牌桶节流 + 并发信号量 + 风控感知退避 + 熔断，统一约束所有 B 站 HTTP 调用，
避免多个调度任务并发尖峰触发风控。

设计要点：
- `guard(category)` 上下文管理器：acquire 节流 + 并发上限，yield 后由调用方记录结果。
- 风控识别来自 `ResponseCodeException.code`（如 -352/-101）与 `NetworkException.status`
  （如 412）。调用方在捕获异常后调 `record_risk()`，成功调 `record_success()`。
- 连续命中风控达到阈值即熔断该类别一段时间，`guard()` 会抛出 `CircuitOpenError`，
  替代旧的"盲目 sleep(60) 重试"。
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Optional, Set


class CircuitOpenError(RuntimeError):
    """熔断开启时抛出，调用方应放弃本次调用并稍后再试。"""

    def __init__(self, category: str, retry_after: float):
        self.category = category
        self.retry_after = retry_after
        super().__init__(
            f"熔断开启（{category}），约 {retry_after:.0f}s 后恢复"
        )


# bilibili-api 的风控/网络异常（延迟导入，避免在模块加载期硬依赖）
def _load_risk_exception_types():
    try:
        from bilibili_api.utils.network import (
            ResponseCodeException,
            NetworkException,
        )

        return ResponseCodeException, NetworkException
    except Exception:
        return None, None


class BilibiliRateLimiter:
    """B 站 API 全局限流器。

    线程/协程安全（内部用 asyncio 原语）。每个事件循环应共享同一个实例。
    """

    def __init__(
        self,
        qps: float = 1.0,
        concurrency: int = 2,
        backoff_base: float = 60.0,
        backoff_max: float = 600.0,
        circuit_trips: int = 3,
        circuit_cooldown: float = 600.0,
        risk_codes: Optional[Set[int]] = None,
    ):
        self.min_interval: float = (1.0 / qps) if qps > 0 else 0.0
        self.semaphore = asyncio.Semaphore(max(1, concurrency))
        self.backoff_base = float(backoff_base)
        self.backoff_max = float(backoff_max)
        self.circuit_trips = max(1, int(circuit_trips))
        self.circuit_cooldown = float(circuit_cooldown)
        self.risk_codes: Set[int] = set(risk_codes or {-352, -101, -403, 412})

        self._last_call_at: float = 0.0
        self._throttle_lock = asyncio.Lock()

        # 按调用类别（如 feed_all / feed_space / comments）维护退避/熔断状态
        self._backoff_level: Dict[str, int] = {}
        self._risk_streak: Dict[str, int] = {}
        self._circuit_until: Dict[str, float] = {}

        self.logger = logging.getLogger(f"{__name__}.BilibiliRateLimiter")

    # ------------------------------------------------------------------
    # 节流与并发
    # ------------------------------------------------------------------
    async def _throttle(self) -> None:
        """令牌桶：保证全局最小调用间隔。"""
        async with self._throttle_lock:
            now = time.monotonic()
            wait = self._last_call_at + self.min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call_at = time.monotonic()

    def _is_circuit_open(self, category: str) -> Optional[float]:
        until = self._circuit_until.get(category, 0.0)
        if until and time.monotonic() < until:
            return until - time.monotonic()
        if until:
            # 熔断已过期，清理
            self._circuit_until.pop(category, None)
            self._risk_streak[category] = 0
        return None

    @asynccontextmanager
    async def guard(self, category: str = "default"):
        """限流上下文：先检查熔断，再节流，再限定并发。

        用法::

            async with limiter.guard("feed_all"):
                page = await dynamic.get_dynamic_page_info(...)
            limiter.record_success("feed_all")
        """
        remaining = self._is_circuit_open(category)
        if remaining is not None:
            raise CircuitOpenError(category, remaining)
        await self._throttle()
        async with self.semaphore:
            yield

    # ------------------------------------------------------------------
    # 风控记录与退避/熔断
    # ------------------------------------------------------------------
    def classify(self, exc: BaseException) -> bool:
        """判断异常是否为风控/限流信号。"""
        ResponseCodeException, NetworkException = _load_risk_exception_types()
        if ResponseCodeException is not None and isinstance(
            exc, ResponseCodeException
        ):
            return exc.code in self.risk_codes
        if NetworkException is not None and isinstance(exc, NetworkException):
            return exc.status in self.risk_codes
        # 兜底：匹配常见的风控关键字
        msg = str(exc).lower()
        if any(k in msg for k in ("risk", "风控", "412", "-352", "captcha", "验证")):
            return True
        return False

    def record_risk(self, category: str = "default") -> float:
        """记录一次风控命中，返回建议的退避秒数（指数退避）。"""
        level = self._backoff_level.get(category, 0) + 1
        self._backoff_level[category] = level
        streak = self._risk_streak.get(category, 0) + 1
        self._risk_streak[category] = streak

        backoff = min(
            self.backoff_base * (2 ** (level - 1)), self.backoff_max
        )

        if streak >= self.circuit_trips:
            self._circuit_until[category] = (
                time.monotonic() + self.circuit_cooldown
            )
            self.logger.error(
                "B站接口连续命中风控 %d 次，熔断 %s %.0fs",
                streak,
                category,
                self.circuit_cooldown,
            )
        else:
            self.logger.warning(
                "B站接口风控（%s），退避 %.0fs（连续第 %d 次）",
                category,
                backoff,
                streak,
            )
        return backoff

    def record_success(self, category: str = "default") -> None:
        """记录一次成功调用，重置连续风控计数并衰减退避级别。"""
        if self._risk_streak.get(category, 0):
            self._risk_streak[category] = 0
        if self._backoff_level.get(category, 0):
            self._backoff_level[category] = max(
                0, self._backoff_level[category] - 1
            )

    def current_backoff(self, category: str = "default") -> float:
        level = self._backoff_level.get(category, 0)
        if level <= 0:
            return 0.0
        return min(self.backoff_base * (2 ** (level - 1)), self.backoff_max)


def build_rate_limiter_from_env() -> BilibiliRateLimiter:
    """按 config.py 的 env 约定构造限流器（带默认值）。"""
    import os

    def _f(name, default):
        v = os.getenv(name)
        if v is None or v == "":
            return default
        return float(v)

    return BilibiliRateLimiter(
        qps=_f("BILI_RATE_LIMIT_QPS", 1.0),
        concurrency=int(_f("BILI_RATE_LIMIT_CONCURRENCY", 2)),
        backoff_base=_f("BILI_RISK_BACKOFF_BASE", 60.0),
        backoff_max=_f("BILI_RISK_BACKOFF_MAX", 600.0),
        circuit_trips=int(_f("BILI_RISK_CIRCUIT_TRIPS", 3)),
        circuit_cooldown=_f("BILI_RISK_BACKOFF_MAX", 600.0),
    )
