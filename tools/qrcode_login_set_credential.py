# -*- coding: utf-8 -*-
"""扫码登录并写入 B 站凭证到 .env

用途：避免手动从浏览器逐个复制 SESSDATA / bili_jct / buvid3 / DedeUserID / ac_time_value。

依赖：bilibili-api-python（仓库已使用）。

使用：
- 仅打印 .env 片段：uv run python tools/qrcode_login_set_credential.py
- 直接写入项目根目录 .env：uv run python tools/qrcode_login_set_credential.py --write

注意：
- 该脚本会在终端输出二维码；用 B 站 App 扫码确认登录。
- 会输出并/或写入敏感信息，请注意不要把终端内容截图分享。
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from bilibili_api import login_v2

_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_TEMP_DIR = _PROJECT_ROOT / "temp"
_QRCODE_PNG_PATH = _TEMP_DIR / "bilibili_qrcode.png"


def _render_env_block(values: dict[str, str | None]) -> str:
    lines: list[str] = []
    lines.append("# B站Cookie配置")

    order = [
        "SESSDATA",
        "bili_jct",
        "buvid3",
        "buvid4",
        "DedeUserID",
        "DedeUserID__ckMd5",
        "ac_time_value",
    ]
    for k in order:
        v = values.get(k)
        if v:
            lines.append(f"{k}={v}")

    return "\n".join(lines) + "\n"


def _upsert_env_file(env_path: Path, values: dict[str, str | None]) -> None:
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        existing_lines = []

    def normalize_key(line: str) -> str | None:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return None
        if "=" not in stripped:
            return None
        return stripped.split("=", 1)[0].strip()

    key_to_index: dict[str, int] = {}
    for idx, line in enumerate(existing_lines):
        key = normalize_key(line)
        if key:
            key_to_index[key] = idx

    # 保持已有文件结构：优先替换已存在的 key；不存在则追加到末尾
    appended: list[str] = []

    for k, v in values.items():
        if not v:
            continue
        if k in key_to_index:
            existing_lines[key_to_index[k]] = f"{k}={v}\n"
        else:
            appended.append(f"{k}={v}\n")

    if appended:
        if existing_lines and not existing_lines[-1].endswith("\n"):
            existing_lines[-1] = existing_lines[-1] + "\n"
        existing_lines.append("\n# B站Cookie配置（扫码登录自动写入）\n")
        existing_lines.extend(appended)

    env_path.write_text("".join(existing_lines), encoding="utf-8")


async def _login_and_get_values() -> dict[str, str | None]:
    qr = login_v2.QrCodeLogin()
    await qr.generate_qrcode()

    print("\n请使用 B 站 App 扫码登录：\n")
    print(qr.get_qrcode_terminal())

    # 终端二维码使用 ANSI 背景色块渲染，部分终端主题/设置会导致“看起来像空白”。
    # 为了兜底，同时写出 PNG 文件，用户可直接打开。
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    qr.get_qrcode_picture().to_file(str(_QRCODE_PNG_PATH))
    print(f"\n如果终端二维码显示为空白，请打开：{_QRCODE_PNG_PATH}")

    last_state = None
    while True:
        state = await qr.check_state()
        if state == login_v2.QrCodeLoginEvents.DONE:
            cred = qr.get_credential()
            return {
                "SESSDATA": getattr(cred, "sessdata", None),
                "bili_jct": getattr(cred, "bili_jct", None),
                "buvid3": getattr(cred, "buvid3", None),
                "buvid4": getattr(cred, "buvid4", None),
                "DedeUserID": getattr(cred, "dedeuserid", None),
                # bilibili-api-python 不一定总能给到 ckMd5
                "DedeUserID__ckMd5": getattr(cred, "dedeuserid_ckmd5", None),
                "ac_time_value": getattr(cred, "ac_time_value", None),
            }
        if state == login_v2.QrCodeLoginEvents.TIMEOUT:
            raise RuntimeError("二维码已过期，请重新运行脚本")

        # 兼容当前版本事件：SCAN/CONF（已扫码/已确认）
        if state != last_state:
            last_state = state
            if state == login_v2.QrCodeLoginEvents.SCAN:
                print("已扫码，等待 App 确认...")
            elif state == login_v2.QrCodeLoginEvents.CONF:
                print("已确认，正在登录...")

        await asyncio.sleep(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="B站扫码登录并写入 .env")
    parser.add_argument(
        "--write",
        action="store_true",
        help="将获取到的凭证写入项目根目录 .env（默认只打印）",
    )
    args = parser.parse_args()

    values = asyncio.run(_login_and_get_values())

    print("\n获取到的 .env 片段如下（注意保密）：\n")
    print(_render_env_block(values))

    if args.write:
        _upsert_env_file(_ENV_PATH, values)
        print(f"\n[OK] 已写入: {_ENV_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
