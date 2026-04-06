#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速测试：使用新凭证拉取动态"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bilibili_api import user

from config import build_bilibili_credential


async def main():
    print("\n=== 测试：使用新凭证拉取动态 ===\n")

    # 1. 加载凭证
    cred = build_bilibili_credential()
    if not cred:
        print("❌ 未找到凭证")
        return

    print("✓ 凭证已加载")

    # 2. 加载创作者列表
    with open("data/bilibili_creators.json", "r", encoding="utf-8") as f:
        creators = json.load(f)

    if not creators:
        print("❌ 创作者列表为空")
        return

    # 3. 测试拉取第一个创作者的动态
    test_creator = creators[0]
    uid = test_creator["uid"]
    name = test_creator["name"]

    print(f"测试创作者: {name} (UID: {uid})\n")

    u = user.User(uid, credential=cred)

    try:
        dynamics = await u.get_dynamics()

        # bilibili_api 返回的是旧版格式，使用 'cards' 而不是 'items'
        if dynamics and "cards" in dynamics:
            items = dynamics["cards"]
            print(f"✅ 成功拉取动态！共 {len(items)} 条\n")

            # 显示前3条
            for i, item in enumerate(items[:3], 1):
                desc = item.get("desc", {})
                dynamic_id = desc.get("dynamic_id_str") or desc.get("dynamic_id")
                timestamp = desc.get("timestamp", 0)

                from datetime import datetime

                pub_time = (
                    datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    if timestamp
                    else "未知时间"
                )

                print(f"  [{i}] ID: {dynamic_id}")
                print(f"      时间: {pub_time}")

                # 尝试获取内容
                card_str = item.get("card", "")
                if card_str:
                    import json as js

                    card = js.loads(card_str) if isinstance(card_str, str) else card_str

                    # 图文动态
                    if "item" in card and "description" in card["item"]:
                        desc_text = card["item"]["description"]
                        preview = (
                            desc_text[:50] + "..." if len(desc_text) > 50 else desc_text
                        )
                        print(f"      内容: {preview}")
                    # 视频动态
                    elif "title" in card:
                        print(f"      标题: {card['title']}")
                print()
        else:
            print("⚠️ 返回数据格式异常")
            print(f"返回内容键: {dynamics.keys() if dynamics else 'None'}")

    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
