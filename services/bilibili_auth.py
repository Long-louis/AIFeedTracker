# -*- coding: utf-8 -*-
"""
B站认证和Cookie管理模块

实现B站Cookie自动刷新机制
参考文档: https://socialsisteryi.github.io/bilibili-API-collect/docs/login/cookie_refresh.html
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import aiohttp

from config import apply_bilibili_config


class BilibiliAuth:
    """B站认证管理类"""

    # API端点
    CHECK_COOKIE_URL = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
    REFRESH_COOKIE_URL = (
        "https://passport.bilibili.com/x/passport-login/web/cookie/refresh"
    )
    CONFIRM_REFRESH_URL = (
        "https://passport.bilibili.com/x/passport-login/web/confirm/refresh"
    )

    # 存储路径
    AUTH_DATA_PATH = Path("data/bilibili_auth.json")
    QR_CODE_PATH = Path("temp/bilibili_qrcode.png")

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.auth_data = self._load_auth_data()
        self._qr_login = None

    def _load_auth_data(self) -> dict:
        """加载认证数据"""
        if self.AUTH_DATA_PATH.exists():
            try:
                with open(self.AUTH_DATA_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"加载认证数据失败: {e}")
        return {}

    def _save_auth_data(self) -> None:
        """保存认证数据"""
        try:
            os.makedirs(self.AUTH_DATA_PATH.parent, exist_ok=True)
            with open(self.AUTH_DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(self.auth_data, f, ensure_ascii=False, indent=2)
            self.logger.info("认证数据已保存")
        except Exception as e:
            self.logger.error(f"保存认证数据失败: {e}")

    def _apply_credentials(self, values: dict) -> None:
        apply_bilibili_config(values)

    def set_refresh_token(self, refresh_token: str) -> None:
        """
        设置refresh_token

        Args:
            refresh_token: 从登录接口获得的refresh_token
        """
        self.auth_data["refresh_token"] = refresh_token
        self.auth_data["last_refresh_time"] = time.time()
        self._save_auth_data()
        self.logger.info("refresh_token已更新")

    def get_qr_last_notify_ts(self) -> float:
        ts = self.auth_data.get("qr_last_notify_ts")
        if isinstance(ts, (int, float)):
            return float(ts)
        return 0.0

    def set_qr_last_notify_ts(self, ts: float) -> None:
        self.auth_data["qr_last_notify_ts"] = float(ts)
        self._save_auth_data()

    def get_qr_pending_notify_reason(self) -> Optional[str]:
        reason = self.auth_data.get("qr_pending_notify_reason")
        if isinstance(reason, str) and reason:
            return reason
        return None

    def set_qr_pending_notify_reason(self, reason: str) -> None:
        self.auth_data["qr_pending_notify_reason"] = str(reason)
        self._save_auth_data()

    def clear_qr_pending_notify_reason(self) -> None:
        if "qr_pending_notify_reason" not in self.auth_data:
            return
        self.auth_data.pop("qr_pending_notify_reason", None)
        self._save_auth_data()

    def set_credential_values(self, values: dict) -> None:
        """写入并应用B站凭证（不写 .env）。"""
        for k, v in values.items():
            if not v:
                continue
            self.auth_data[str(k)] = str(v)
        self._save_auth_data()
        self._apply_credentials(values)

    def get_refresh_token(self) -> Optional[str]:
        """
        获取refresh_token
        优先使用ac_time_value（兼容B站refresh_token），然后再回退
        """
        # 优先从环境变量读取（.env文件）
        import os

        env_ac_time_value = os.getenv("ac_time_value")
        if env_ac_time_value:
            return env_ac_time_value

        env_refresh_token = os.getenv("refresh_token")
        if env_refresh_token:
            return env_refresh_token

        # 如果env中没有，从json文件读取（兼容旧版本）
        return self.auth_data.get("ac_time_value") or self.auth_data.get(
            "refresh_token"
        )

    async def check_need_refresh(self, cookie: str) -> Tuple[bool, Optional[int]]:
        """
        检查Cookie是否需要刷新

        Args:
            cookie: 当前Cookie字符串

        Returns:
            (是否需要刷新, 时间戳)
        """
        try:
            # 提取bili_jct作为csrf
            csrf = self._extract_bili_jct(cookie)

            params = {}
            if csrf:
                params["csrf"] = csrf

            # 导入统一配置的User-Agent
            from config import USER_AGENT

            headers = {
                "User-Agent": USER_AGENT,
                "Cookie": cookie,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.CHECK_COOKIE_URL, params=params, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 0:
                            result = data.get("data", {})
                            need_refresh = result.get("refresh", False)
                            timestamp = result.get("timestamp")

                            self.logger.info(
                                f"Cookie检查完成: need_refresh={need_refresh}, timestamp={timestamp}"
                            )
                            return need_refresh, timestamp
                        else:
                            self.logger.error(f"检查Cookie失败: {data.get('message')}")
                    else:
                        self.logger.error(f"检查Cookie失败，HTTP状态码: {resp.status}")

        except Exception as e:
            self.logger.error(f"检查Cookie时出错: {e}")

        return False, None

    async def refresh_cookie(
        self, old_cookie: str, correspond_path: str
    ) -> Optional[Tuple[str, str]]:
        """
        刷新Cookie

        Args:
            old_cookie: 旧Cookie
            correspond_path: CorrespondPath（由时间戳生成）

        Returns:
            (新Cookie, 新refresh_token) 或 None
        """
        try:
            refresh_token = self.get_refresh_token()
            if not refresh_token:
                self.logger.warning("没有refresh_token，无法刷新Cookie")
                return None

            # 提取csrf
            csrf = self._extract_bili_jct(old_cookie)
            if not csrf:
                self.logger.error("无法从Cookie中提取bili_jct")
                return None

            # 构造请求
            data = {
                "csrf": csrf,
                "refresh_csrf": correspond_path,
                "refresh_token": refresh_token,
                "source": "main_web",
            }

            # 导入统一配置的User-Agent
            from config import USER_AGENT

            headers = {
                "User-Agent": USER_AGENT,
                "Cookie": old_cookie,
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.REFRESH_COOKIE_URL, data=data, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("code") == 0:
                            data = result.get("data", {})
                            new_refresh_token = data.get("refresh_token")

                            # 从响应头中获取新Cookie
                            new_cookie = self._merge_cookies(old_cookie, resp.cookies)

                            self.logger.info("Cookie刷新成功")
                            return new_cookie, new_refresh_token
                        else:
                            self.logger.error(
                                f"刷新Cookie失败: {result.get('message')}"
                            )
                    else:
                        self.logger.error(f"刷新Cookie失败，HTTP状态码: {resp.status}")

        except Exception as e:
            self.logger.error(f"刷新Cookie时出错: {e}")

        return None

    async def confirm_refresh(self, new_cookie: str, old_refresh_token: str) -> bool:
        """
        确认Cookie刷新

        Args:
            new_cookie: 新Cookie
            old_refresh_token: 旧的refresh_token

        Returns:
            是否成功
        """
        try:
            csrf = self._extract_bili_jct(new_cookie)
            if not csrf:
                self.logger.error("无法从新Cookie中提取bili_jct")
                return False

            data = {
                "csrf": csrf,
                "refresh_token": old_refresh_token,
            }

            # 导入统一配置的User-Agent
            from config import USER_AGENT

            headers = {
                "User-Agent": USER_AGENT,
                "Cookie": new_cookie,
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.CONFIRM_REFRESH_URL, data=data, headers=headers, timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("code") == 0:
                            self.logger.info("确认Cookie刷新成功")
                            return True
                        else:
                            self.logger.error(f"确认刷新失败: {result.get('message')}")
                    else:
                        self.logger.error(f"确认刷新失败，HTTP状态码: {resp.status}")

        except Exception as e:
            self.logger.error(f"确认刷新时出错: {e}")

        return False

    async def auto_refresh_if_needed(self, current_cookie: str) -> Optional[str]:
        """
        自动检查并刷新Cookie（如果需要）

        Args:
            current_cookie: 当前Cookie

        Returns:
            新Cookie（如果刷新了）或原Cookie
        """
        try:
            # 检查今天是否已经检查过
            last_check = self.auth_data.get("last_check_time", 0)
            current_time = time.time()

            # 如果距离上次检查不到1小时，跳过
            if current_time - last_check < 3600:
                self.logger.debug("Cookie最近已检查，跳过")
                return current_cookie

            # 检查是否需要刷新
            need_refresh, timestamp = await self.check_need_refresh(current_cookie)

            # 更新检查时间
            self.auth_data["last_check_time"] = current_time
            self._save_auth_data()

            if not need_refresh:
                self.logger.info("Cookie无需刷新")
                return current_cookie

            # 需要刷新
            self.logger.info("检测到Cookie需要刷新，开始刷新流程...")

            # 生成CorrespondPath（简化版，实际应该使用wasm算法）
            correspond_path = self._generate_correspond_path(timestamp)

            # 刷新Cookie
            refresh_result = await self.refresh_cookie(current_cookie, correspond_path)
            if not refresh_result:
                self.logger.error("Cookie刷新失败")
                return current_cookie

            new_cookie, new_refresh_token = refresh_result

            # 保存旧的refresh_token用于确认
            old_refresh_token = self.get_refresh_token()

            # 更新refresh_token
            self.set_refresh_token(new_refresh_token)

            # 确认刷新
            if old_refresh_token:
                confirmed = await self.confirm_refresh(new_cookie, old_refresh_token)
                if not confirmed:
                    self.logger.warning("确认刷新失败，但Cookie可能已更新")

            self.logger.info("Cookie自动刷新完成！")
            return new_cookie

        except Exception as e:
            self.logger.error(f"自动刷新Cookie时出错: {e}")
            return current_cookie

    def has_active_qr_login(self) -> bool:
        return self._qr_login is not None

    async def start_qr_login(self) -> str:
        """生成二维码并落盘，返回二维码文件路径。"""
        from bilibili_api import login_v2

        self._qr_login = login_v2.QrCodeLogin()
        await self._qr_login.generate_qrcode()

        os.makedirs(self.QR_CODE_PATH.parent, exist_ok=True)
        self._qr_login.get_qrcode_picture().to_file(str(self.QR_CODE_PATH))
        self.auth_data["qr_login_ts"] = time.time()
        self._save_auth_data()
        return str(self.QR_CODE_PATH)

    async def poll_qr_login(self) -> Tuple[str, Optional[dict]]:
        """轮询扫码状态，返回 (state, values)。"""
        from bilibili_api import login_v2

        if not self._qr_login:
            return "none", None

        state = await self._qr_login.check_state()

        if state == login_v2.QrCodeLoginEvents.TIMEOUT:
            self._qr_login = None
            return "timeout", None

        if state != login_v2.QrCodeLoginEvents.DONE:
            return "pending", None

        cred = self._qr_login.get_credential()
        self._qr_login = None
        values = {
            "SESSDATA": getattr(cred, "sessdata", None),
            "bili_jct": getattr(cred, "bili_jct", None),
            "buvid3": getattr(cred, "buvid3", None),
            "buvid4": getattr(cred, "buvid4", None),
            "DedeUserID": getattr(cred, "dedeuserid", None),
            "DedeUserID__ckMd5": getattr(cred, "dedeuserid_ckmd5", None),
            "ac_time_value": getattr(cred, "ac_time_value", None),
        }
        return "done", values

    @staticmethod
    def _extract_bili_jct(cookie: str) -> Optional[str]:
        """从Cookie字符串中提取bili_jct"""
        for item in cookie.split(";"):
            item = item.strip()
            if item.startswith("bili_jct="):
                return item.split("=", 1)[1]
        return None

    @staticmethod
    def _merge_cookies(old_cookie: str, new_cookies) -> str:
        """合并旧Cookie和新Cookie"""
        # 解析旧Cookie
        cookie_dict = {}
        for item in old_cookie.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookie_dict[key] = value

        # 更新新Cookie
        for key, morsel in new_cookies.items():
            cookie_dict[key] = morsel.value

        # 重新组装
        return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

    @staticmethod
    def _generate_correspond_path(timestamp: Optional[int] = None) -> str:
        """
        生成CorrespondPath

        注意：这是简化版本，完整实现需要使用B站的wasm算法
        文档中的wasm文件：https://s1.hdslb.com/bfs/static/jinkela/long/wasm/wasm_rsa_encrypt_bg.wasm

        Args:
            timestamp: 毫秒时间戳

        Returns:
            CorrespondPath字符串
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        # 简化版本：使用时间戳的十六进制
        # 实际应该调用wasm算法
        return hex(timestamp)[2:]


# 使用示例
async def example_usage():
    """使用示例"""
    from config import build_bilibili_cookie

    auth = BilibiliAuth()

    # 1. 获取当前Cookie
    current_cookie = build_bilibili_cookie()

    # 2. 自动检查并刷新（如果需要）
    new_cookie = await auth.auto_refresh_if_needed(current_cookie)

    if new_cookie != current_cookie:
        print("Cookie已更新！")
        print("新Cookie:", new_cookie[:50], "...")
        # TODO: 更新到.env文件
    else:
        print("Cookie无需更新")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
