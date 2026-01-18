#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试飞书应用配置是否正确加载"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import FEISHU_APP_ID, FEISHU_APP_SECRET
from services.feishu import FeishuBot

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def main():
    print("\n=== 测试飞书应用配置 ===\n")

    # 1. 检查配置加载
    print(f"FEISHU_APP_ID: {FEISHU_APP_ID}")
    print(f"FEISHU_APP_SECRET: {FEISHU_APP_SECRET[:10]}... (已隐藏)")
    print()

    # 2. 检查 FeishuBot 初始化
    bot = FeishuBot()
    print(f"FeishuBot._image_upload_app_cfg: {bot._image_upload_app_cfg}")
    print()

    # 3. 测试图片上传（如果有本地二维码）
    qr_path = project_root / "temp" / "bilibili_qrcode.png"
    if qr_path.exists():
        print(f"发现二维码文件: {qr_path}")
        image_key = await bot.upload_local_image(str(qr_path))
        if image_key:
            print(f"✅ 图片上传成功: {image_key}")
        else:
            print("❌ 图片上传失败")
    else:
        print(f"⚠️ 未找到二维码文件: {qr_path}")


if __name__ == "__main__":
    asyncio.run(main())
