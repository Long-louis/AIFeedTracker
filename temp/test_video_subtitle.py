# -*- coding: utf-8 -*-
"""测试指定视频的字幕获取 - 详细版"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bilibili_api import video

from config import build_bilibili_credential


async def main():
    # 你提到的两个视频
    test_bvids = [
        "BV1jNBUBZEB9",
        "BV1ZPBUBtEgE",
    ]

    credential = build_bilibili_credential()

    for bvid in test_bvids:
        print("=" * 70)
        print(f"测试: {bvid}")
        print("=" * 70)

        v = video.Video(bvid=bvid, credential=credential)

        # 获取视频信息
        info = await v.get_info()
        title = info.get("title", "未知")
        cid = info.get("cid")
        pubdate = info.get("pubdate", 0)
        duration = info.get("duration", 0)

        # 计算发布时间
        pub_time = datetime.fromtimestamp(pubdate)
        now = datetime.now()
        time_diff = now - pub_time
        hours_ago = time_diff.total_seconds() / 3600

        print(f"标题: {title}")
        print(f"发布时间: {pub_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"距今: {hours_ago:.1f} 小时")
        print(f"视频时长: {duration // 60}分{duration % 60}秒")

        # 获取字幕信息
        subtitle_info = await v.get_subtitle(cid=cid)
        subtitles = subtitle_info.get("subtitles", [])

        if subtitles:
            print(f"\n✅ 找到 {len(subtitles)} 个字幕:")
            for i, sub in enumerate(subtitles):
                print(
                    f"  [{i + 1}] {sub.get('lan_doc', '未知')} ({sub.get('lan', '')})"
                )
        else:
            print("\n❌ 没有找到任何字幕（B站AI字幕可能还在生成中）")

        print()


if __name__ == "__main__":
    asyncio.run(main())
