# 监控聚合流改造实现文档

> 目标：用 B 站聚合动态流接口取代"逐博主轮询"，把动态 API 调用数从 `博主数 × 频率`
> 降为**每轮固定 1 次**；同时引入全局限流与风控退避熔断；并支持分层延迟
> （盘中实时博主近实时、收盘后复盘视频按小时处理），在规避风控的同时保持关键时效性。

---

## 一、背景与问题

### 1.1 现状

当前监控对**每个博主单独建一个调度任务**，逐个拉取其个人空间动态：

- 调度入口 `services/monitor.py:1949` `start_monitoring()`：为每个 Creator 注册独立
  APScheduler job（cron 或 interval），彼此无协调。
- 单博主一次轮询 `services/monitor.py:1544` `process_creator()` →
  `services/monitor.py:1513` `fetch_user_space_dynamics()` →
  `bilibili_api.user.User.get_dynamics_new()`，命中的是个人空间接口
  `GET https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space`，**每个博主每轮 1 次调用**。
- interval 下限仅 30 秒（`services/monitor.py:2021` `max(30, ...)`）。
- 开启 `enable_comments` 时，每轮还会额外产生最多约 20 次评论接口调用
  （`services/monitor.py:1587` `_check_recent_pinned_comments` 与
  `services/monitor.py:1590` `_poll_creator_comments`，命中 `/v2/reply`）。

### 1.2 根因

调用数随博主数线性增长（`博主数 × 频率`），所有调用共用同一 SESSDATA + buvid3 + WBI
签名指纹，且：

1. **无全局并发/速率限制**：仓库内无 `Semaphore`/令牌桶/节流；多个 job 同时到点会瞬间并发。
2. **无风控感知退避**：异常时只盲目 `sleep(60)` 重试（`services/monitor.py:1947`），
   不区分风控码（-352 验证码 / -101 未登录 / HTTP 412）。
3. **冗余调用**：即使博主无新动态也每轮全量拉取；评论对近期 5 条逐个翻页。

这是引发风控的直接原因。

---

## 二、总体方案

采用 **档位 A（聚合流）+ 档位 C（限流/退避熔断）+ 分层延迟**，一次性落地：

| 模块 | 做什么 | 收益 |
|---|---|---|
| 档位 A 聚合流 | 用 `/feed/all` 一次拉取**全部关注博主**的合并动态流，按 UID 过滤后复用现有派发逻辑 | 调用数与博主数解耦，每轮固定 1 次 |
| 分层延迟 | 盘中实时博主快周期、收盘后复盘视频慢周期/延迟总结 | 关键时效不丢，非关键请求大幅降低 |
| 档位 C 限流 | 全局令牌桶 + 并发信号量 + 风控退避 + 熔断 | 杜绝并发尖峰，命中风控后自动降速而非盲重试 |

**前置事实（已确认）**：被监控的博主都已在账号关注列表内，因此聚合流 `/feed/all`
必然能取到他们的动态。

---

## 三、关键接口调研（bilibili-api-python 已封装，本项目未使用）

均在 `bilibili_api.dynamic` 模块，已确认存在于当前 venv：

| 函数 | 实际端点 | 作用 |
|---|---|---|
| `get_dynamic_page_info(credential, _type=DynamicType.ALL, offset=...)` | `GET /x/polymer/web-dynamic/v1/feed/all` | **全部关注动态聚合流**，返回 `{items, has_more, offset}` |
| `get_new_dynamic_users(credential)` | `GET /dynamic_svr/v1/dynamic_svr/w_dyn_uplist` | "有更新的关注者"红点列表（差分前置过滤，可选） |
| `get_dynamic_page_UPs_info(credential)` | `GET /x/polymer/web-dynamic/v1/portal` | 动态页 UP 主列表（含未读计数，用于关注列表校验） |

- 聚合流 item 与个人空间 item **同属 polymer 格式**，作者 UID 在
  `item["modules"]["module_author"]["mid"]`；现有
  `services/monitor.py:1704` `_process_dynamic_item(item, creator)` 可直接复用。
- 去重状态 `JsonState.get_last_seen(uid)` / `set_last_seen(uid)`
  （`services/monitor.py:161` / `:164`）按 UID 存放，聚合模式无需改动即可复用。
- 时效性：`/feed/all` 与 `/feed/space` 同源 polymer 接口，服务端更新延迟一致，**改用聚合流不损失时效**。

---

## 四、详细设计

### 4.1 聚合流拉取（档位 A）

新增方法（放在 `MonitorService` 内，紧邻 `fetch_user_space_dynamics`）：

```python
async def fetch_aggregated_feed(self, offset: Optional[str] = None) -> Dict[str, Any]:
    """拉取全部关注博主的聚合动态流（单次调用）"""
    # 命中 GET /x/polymer/web-dynamic/v1/feed/all
    page = await dynamic.get_dynamic_page_info(
        credential=self.credential,
        _type=dynamic.DynamicType.ALL,
        offset=offset,
    )
    items = page.get("items", []) or []
    return {
        "code": 0,
        "data": {"items": items},
        "has_more": page.get("has_more"),
        "offset": page.get("offset"),
    }
```

新增派发方法 `process_aggregated_feed()`：

1. 调 `fetch_aggregated_feed()` 拿到全部 items（单页通常约 30 条）。
2. 解析每条 `item["modules"]["module_author"]["mid"]`，按 UID 分组。
3. 只保留 UID 出现在当前 `bilibili_creators.json` 的条目（其余忽略）。
4. 对每个匹配到的 Creator，复用现有逻辑：按 `get_publish_timestamp` 排序、
   比较 `state.get_last_seen(uid)`、对新动态调用 `_process_dynamic_item(item, creator)`
   （`services/monitor.py:1704`），处理完 `set_last_seen` + `state.save()`。
5. 评论轮询（`_check_recent_pinned_comments` / `_poll_creator_comments`）改为
   **只对该博主"有新动态"时触发**，避免每轮对全员翻页。

> 注意：聚合流单页条数有限。本项目只关心"新"动态（配合 last_seen 去重），
> 单页足够覆盖一个轮询周期；若某博主高产导致漏旧，可用返回的 `offset` 翻页补齐当前窗口。

### 4.2 分层延迟模型

两个正交维度：

**维度一：时间窗口 → 决定轮询周期**

聚合流是单轮询器，无法给单个博主更低延迟，因此轮询周期**纯按时间窗口控制**
（不再依赖 per-creator `latency_tier`）：

| 窗口 | 含义 | 周期 |
|---|---|---|
| 盘中（活跃） | 交易日 09:15–15:00 | `FEED_POLL_FAST_SECONDS`（默认 90s） |
| 收盘后/日间 | 非盘中但非深夜 | `FEED_POLL_NORMAL_SECONDS`（默认 600s） |
| 深夜 | 凌晨等 | `FEED_POLL_QUIET_SECONDS`（默认 3600s） |

> 每个周期还会叠加随机抖动（`FEED_POLL_JITTER_PCT`，默认 ±25%），
> 避免固定周期成为风控指纹。

**维度二：创作者 tier（保留字段，主要用于总结时机）**

- `latency_tier`：保留字段，聚合模式下不再影响轮询频率（频率由时间窗口决定）。
- `summarize_mode`: `"immediate"`（检测到即总结，默认）/ `"deferred"`（进入按小时批量队列）。

新增周期控制器：

```python
def _compute_poll_interval(self) -> int:
    now = datetime.now(self._SCHEDULER_TIMEZONE)
    if self._in_market_session(now) and self._has_realtime_creator():
        return self.feed_poll_fast_seconds
    if self._is_quiet_hours(now):
        return self.feed_poll_quiet_seconds
    return self.feed_poll_normal_seconds
```

### 4.3 全局限流与风控退避熔断（档位 C）

新增 `services/bilibili_rate_limiter.py`，提供 `BilibiliRateLimiter`，**所有 B 站 HTTP
调用统一经过它**（聚合流、空间流、评论、用户信息）：

- **令牌桶**：QPS 上限 + 最小间隔（默认 `BILI_RATE_LIMIT_QPS=1`）。
- **并发信号量**：限制同时 in-flight 请求数（默认 `BILI_RATE_LIMIT_CONCURRENCY=2`）。
- **风控感知退避**：识别风控信号触发指数退避（默认
  `BILI_RISK_BACKOFF_BASE=60` → `120` → `300`，上限 `BILI_RISK_BACKOFF_MAX=600`）：
  - 响应 `code` 为 `-352`（验证码风控）/ `-101`（未登录）/ `9999*` 鉴权类
  - HTTP 状态 `412` / `403`
- **熔断**：连续 `BILI_RISK_CIRCUIT_TRIPS`（默认 3）次风控 → 熔断该类调用一段时间并
  飞书告警，替代当前 `services/monitor.py:1947` 的盲目 `sleep(60)`。

接入点（包住我们的 `fetch_*` 方法；bilibili-api 内部请求由我们在外层控制节奏）：

```python
async def fetch_aggregated_feed(self, offset=None):
    async with self.rate_limiter.guard("feed_all"):   # acquire + 退避 + 熔断
        page = await dynamic.get_dynamic_page_info(...)
        self.rate_limiter.observe(page)               # 记录风控码用于退避判定
        return ...
```

同样接入 `fetch_user_space_dynamics`（`:1513`，legacy 模式仍用）与
`services/comment_fetcher.py` 的 `comment.get_comments` 调用点。

### 4.4 配置变更

**环境变量（`.env`，均带默认值，旧配置无需改动即可升级）：**

| 变量 | 默认 | 说明 |
|---|---|---|
| `FEED_MODE` | `aggregated` | `aggregated`（聚合流）/ `legacy`（旧逐博主，一键回退） |
| `FEED_POLL_FAST_SECONDS` | `90` | 盘中快周期 |
| `FEED_POLL_NORMAL_SECONDS` | `600` | 日常周期 |
| `FEED_POLL_QUIET_SECONDS` | `3600` | 深夜周期 |
| `MARKET_SESSION_ENABLED` | `true` | 启用会话窗口感知 |
| `MARKET_SESSION_WINDOWS` | `mon-fri 09:15-15:00` | 盘中窗口 |
| `BILI_RATE_LIMIT_QPS` | `1` | 全局 QPS 上限 |
| `BILI_RATE_LIMIT_CONCURRENCY` | `2` | 全局并发上限 |
| `BILI_RISK_BACKOFF_BASE` | `60` | 退避基数（秒） |
| `BILI_RISK_BACKOFF_MAX` | `600` | 退避上限（秒） |
| `BILI_RISK_CIRCUIT_TRIPS` | `3` | 连续风控熔断阈值 |
| `FEED_SUMMARY_BATCH_CRON` | `0 * * * *` | 延迟总结批量队列（每小时） |

**Creator 配置（`data/bilibili_creators.json`）新增可选字段：**

```jsonc
{
  "uid": 123456,
  "name": "实时股票操作博主",
  "latency_tier": "realtime",     // 盘中近实时（默认 "normal"）
  "summarize_mode": "immediate",  // 默认；复盘类可设 "deferred"
  "feishu_channel": "app:default"
}
```

`crons` / `check_interval` 保留，仅在 `FEED_MODE=legacy` 时生效。

---

## 五、落地步骤（按文件）

1. **新增 `services/bilibili_rate_limiter.py`**
   - 实现 `BilibiliRateLimiter`（令牌桶 + 信号量 + 退避 + 熔断 + `guard()` 上下文 +
     `observe()` 记录风控码）。

2. **`services/monitor.py`**
   - `Creator` dataclass（`:100`）新增 `latency_tier: str = "normal"` 与
     `summarize_mode: str = "immediate"`。
   - 新增 `fetch_aggregated_feed()` 与 `process_aggregated_feed()`（见 4.1）。
   - 新增 `_compute_poll_interval()` / `_in_market_session()` /
     `_has_realtime_creator()` / `_is_quiet_hours()`。
   - 新增延迟总结队列 `_summary_queue` 与 `_drain_summary_queue()`（由批量 cron 触发）。
   - 改造 `start_monitoring()`（`:1949`）：`FEED_MODE=aggregated` 时注册**单个聚合 job**
     （周期由 `_compute_poll_interval` 动态决定，用自调度循环而非固定 interval trigger）
     + 可选延迟总结 job；`FEED_MODE=legacy` 时走原 `_setup_creator_jobs`（`:1992`）逻辑。
   - `_prime_last_seen()`（`:2140`）兼容聚合模式（聚合模式下同样按 UID 对齐游标）。
   - `load_creators_from_file()`（`:2167`）解析 `latency_tier` / `summarize_mode`。
   - 在 `fetch_user_space_dynamics`（`:1513`）与新聚合方法接入 `rate_limiter.guard()`。

3. **`config.py`**
   - 读取上述新 env，提供带默认值的配置属性（沿用现有配置装配风格）。

4. **`services/comment_fetcher.py`**
   - 在 `comment.get_comments` 调用点（`:139` / `:562` / `:630`）接入
     `rate_limiter.guard()`，统一节流。

5. **`data/bilibili_creators.json.example`**
   - 补 `latency_tier` / `summarize_mode` 示例字段。

6. **`env.example`**
   - 追加上述新 env 及注释。

7. **关注列表校验（启动时）**
   - 用 `get_dynamic_page_UPs_info` 或聚合首屏结果，校验配置 UID 是否都在关注列表；
     缺失则飞书告警（不阻断启动）。

---

## 六、兼容性与回滚

- `FEED_MODE=legacy` 完整保留旧的逐博主调度，**一行 env 切回**。
- Creator 新字段缺省即等同当前行为，用户无需改配置即可升级。
- 旧 `crons`/`check_interval` 在 legacy 模式照常生效。
- `BilibiliRateLimiter` 即使在 legacy 模式也生效（限流对两种模式都有益）。

---

## 七、测试策略

- **单测 `BilibiliRateLimiter`**：令牌桶/并发/退避递增/熔断触发与恢复（mock 时间与响应码）。
- **单测 `_compute_poll_interval`**：覆盖 盘中+realtime / 收盘 / 深夜 各组合。
- **单测 `process_aggregated_feed`**：mock `get_dynamic_page_info`，验证按 UID 分组、
  去重（last_seen）、未关注 UID 被过滤、realtime/normal 派发路径。
- **聚合 E2E**：参考 `tests/test_video_kb_simulated_e2e.py` 的 mock 思路，模拟聚合流
  返回 + 总结器 + 飞书写入，端到端跑 `MonitorService`。
- **真机验证**：`uv run python main.py --mode monitor --once`（聚合模式）跑一轮确认派发正常。

运行测试：`uv run python -m unittest discover -s tests -p "test_*.py" -q`

---

## 八、风险与注意事项

- **关注列表漂移**：用户取关某博主 → 聚合流缺失该博主动态。由启动关注列表校验 +
  飞书告警兜底（不阻断）。
- **聚合流单页上限**：单页约 30 条；本项目只追"新"动态且按 last_seen 去重，单页足够；
  高产博主场景必要时用 `offset` 翻页补齐当前窗口。
- **bilibili-api 版本依赖**：`get_dynamic_page_info` / `DynamicType.ALL` 依赖当前 venv
  版本；升级 `bilibili-api-python` 后需回归聚合流相关测试。
- **风控码识别需持续维护**：B 站风控策略会变化，退避/熔断的风控码清单应可配置
  （放入 env 而非硬编码），便于后续调整。
