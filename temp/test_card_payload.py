# -*- coding: utf-8 -*-
"""测试飞书卡片 payload 构建"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置测试环境变量
os.environ["FEISHU_TEMPLATE_ID"] = "AAq0SYiLbvWPh"
os.environ["FEISHU_TEMPLATE_VERSION"] = "1.0.2"
os.environ["FEISHU_CHANNELS_CONFIG"] = "data/feishu_channels.json"

# 重新加载 config 模块
import importlib
import config
importlib.reload(config)

from services.feishu import FeishuBot

def test_card_payload():
    """测试卡片 payload 构建"""
    bot = FeishuBot()
    
    print(f"Template ID: {bot.template_id}")
    print(f"Template Version: {bot.template_version_name}")
    print()
    
    # 测试 _build_template_card 方法
    card = bot._build_template_card(
        influencer="测试博主",
        platform="哔哩哔哩",
        markdown_content="这是测试内容",
        addition_title="发布新视频",
        addition_subtitle="",
    )
    
    print("=== 构建的卡片数据 ===")
    print(json.dumps(card, indent=2, ensure_ascii=False))
    print()
    
    # 检查关键字段
    template_variable = card["data"]["template_variable"]
    print("=== template_variable 内容 ===")
    for key, value in template_variable.items():
        print(f"  {key}: {repr(value)}")
    
    # 验证 addition_title 是否存在
    if "addition_title" in template_variable:
        print(f"\n✅ addition_title 存在，值为: {repr(template_variable['addition_title'])}")
    else:
        print("\n❌ addition_title 不存在！")
    
    if "addition_subtitle" in template_variable:
        print(f"✅ addition_subtitle 存在，值为: {repr(template_variable['addition_subtitle'])}")
    else:
        print("❌ addition_subtitle 不存在！")

if __name__ == "__main__":
    test_card_payload()
