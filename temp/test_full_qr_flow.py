#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整的QR登录流程测试

测试流程：
1. 清空现有凭证
2. 启动监控服务（会触发QR登录提醒）
3. 等待扫码
4. 验证凭证已更新
5. 验证能正常拉取动态
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.feishu import FeishuBot
from services.monitor import MonitorService


async def main():
    print("=" * 60)
    print("完整QR登录流程测试")
    print("=" * 60)

    # 1. 备份并记录当前凭证
    print("\n步骤 1: 记录当前凭证状态...")
    auth_file = Path("data/bilibili_auth.json")
    backup_file = Path("data/bilibili_auth.json.test_backup")

    old_sessdata = None
    if auth_file.exists():
        import shutil

        shutil.copy(auth_file, backup_file)
        with open(auth_file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            old_sessdata = (
                old_data.get("SESSDATA", "")[:20] if old_data.get("SESSDATA") else None
            )
        print(f"  ✓ 已备份到: {backup_file}")
        if old_sessdata:
            print(f"  ✓ 当前 SESSDATA: {old_sessdata}...")

    # 2. 初始化服务
    print("\n步骤 2: 初始化监控服务...")
    feishu = FeishuBot()
    monitor = MonitorService(feishu_bot=feishu)

    if not monitor.credential:
        print("  ℹ 当前无有效凭证（将触发QR登录）")
    else:
        print("  ℹ 当前有凭证（测试更新流程）")

    # 3. 触发QR登录提醒
    print("\n步骤 3: 触发QR登录提醒...")
    await monitor._notify_qr_login_needed("测试：模拟凭证过期")
    print("  ✓ 已发送QR登录提醒到飞书")
    print("  ℹ 请在飞书中查看二维码并扫描")

    # 4. 轮询等待扫码
    print("\n步骤 4: 等待扫码（最多10分钟）...")
    max_wait = 600  # 10分钟
    wait_interval = 3
    elapsed = 0

    initial_credential_id = id(monitor.credential) if monitor.credential else None

    while elapsed < max_wait:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval

        # 轮询QR登录状态
        await monitor._poll_qr_login_status()

        # 检查凭证是否已更新（比较对象引用）
        current_credential_id = id(monitor.credential) if monitor.credential else None
        if current_credential_id and current_credential_id != initial_credential_id:
            print(f"\n  ✓ 扫码成功！凭证已更新（耗时 {elapsed}s）")
            break

        if elapsed % 15 == 0:
            print(f"  ⏳ 等待中... ({elapsed}s / {max_wait}s)")

    if not monitor.credential or id(monitor.credential) == initial_credential_id:
        print("\n  ✗ 超时：未在规定时间内完成扫码或凭证未更新")
        print("  ℹ 提示：请确保在飞书中扫描了二维码")
        return

    # 5. 验证凭证
    print("\n步骤 5: 验证凭证...")

    # 检查文件是否已保存
    with open(auth_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    new_sessdata = (
        saved_data.get("SESSDATA", "")[:20] if saved_data.get("SESSDATA") else None
    )

    if not new_sessdata:
        print("  ✗ 错误：SESSDATA 未保存到文件")
        return
    print(f"  ✓ SESSDATA 已保存: {new_sessdata}...")

    # 验证是否更新（如果之前有凭证）
    if old_sessdata and new_sessdata == old_sessdata:
        print("  ⚠ 警告：SESSDATA 未发生变化")
    elif old_sessdata:
        print(f"  ✓ SESSDATA 已更新: {old_sessdata}... → {new_sessdata}...")

    # 验证运行时凭证
    from config import BILIBILI_CONFIG

    if not BILIBILI_CONFIG.get("SESSDATA"):
        print("  ✗ 错误：SESSDATA 未应用到运行时配置")
        return
    print(f"  ✓ SESSDATA 已应用到运行时: {BILIBILI_CONFIG['SESSDATA'][:20]}...")

    # 6. 测试拉取动态
    print("\n步骤 6: 测试拉取动态...")

    # 加载创作者列表
    creators_file = Path("data/bilibili_creators.json")
    if not creators_file.exists():
        print("  ⚠ 未找到创作者配置文件，跳过动态拉取测试")
    else:
        with open(creators_file, "r", encoding="utf-8") as f:
            creators_data = json.load(f)

        if not creators_data:
            print("  ⚠ 创作者列表为空，跳过动态拉取测试")
        else:
            # creators_data 是一个 list
            test_creator = creators_data[0]
            test_uid = test_creator["uid"]
            test_name = test_creator["name"]
            print(f"  ℹ 测试拉取 {test_name} (UID: {test_uid}) 的动态...")

            from bilibili_api import user

            u = user.User(int(test_uid), credential=monitor.credential)

            try:
                dynamics = await u.get_dynamics()
                if dynamics and "items" in dynamics:
                    print(f"  ✓ 成功拉取动态！共 {len(dynamics['items'])} 条")
                else:
                    print("  ⚠ 动态列表为空")
            except Exception as e:
                print(f"  ✗ 拉取动态失败: {e}")
                return

    print("\n" + "=" * 60)
    print("✅ 全部测试通过！")
    print("=" * 60)
    print("\n提示：")
    print("  - 凭证已保存到 data/bilibili_auth.json")
    print(f"  - 原凭证备份在 {backup_file}")
    print("  - 如需恢复，运行:")
    print(f"    cp {backup_file} {auth_file}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n测试已中断")
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback

        traceback.print_exc()
