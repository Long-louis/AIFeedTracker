# -*- coding: utf-8 -*-
"""
B站登录信息检查脚本

检查当前.env文件中配置的B站登录凭证是否有效
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import BILIBILI_CONFIG, build_bilibili_credential
from services.bilibili_auth import BilibiliAuth


async def check_bilibili_auth():
    """检查B站认证状态"""

    print("=" * 60)
    print("B站登录信息检查")
    print("=" * 60)

    # 1. 检查配置是否存在
    print("\n[1] 检查配置文件...")
    credential = build_bilibili_credential()

    if not credential:
        print("❌ 未找到有效的B站登录配置")
        print("请检查.env文件中的以下配置:")
        print("  - SESSDATA")
        print("  - bili_jct")
        print("  - buvid3")
        print("  - buvid4")
        print("  - DedeUserID")
        return False

    print("✅ 配置文件存在")
    print(f"   DedeUserID: {BILIBILI_CONFIG.get('DedeUserID')}")
    print(f"   SESSDATA: {BILIBILI_CONFIG.get('SESSDATA')[:20]}...")

    # 2. 检查Cookie是否需要刷新
    print("\n[2] 检查Cookie状态...")
    auth = BilibiliAuth()

    try:
        from config import build_bilibili_cookie

        cookie = build_bilibili_cookie()

        if not cookie:
            print("❌ 无法构建Cookie")
            return False

        need_refresh, timestamp = await auth.check_need_refresh(cookie)

        if need_refresh is None:
            print("❌ Cookie检查失败 - 登录信息可能已失效")
            print("\n可能的原因:")
            print("  1. SESSDATA已过期")
            print("  2. Cookie格式错误")
            print("  3. 网络问题")
            print("\n建议操作:")
            print("  1. 重新获取B站登录信息（参考 docs/BILIBILI_SETUP.md）")
            print("  2. 检查网络连接")
            return False

        if need_refresh:
            print("⚠️  Cookie需要刷新")

            # 检查是否有refresh_token
            refresh_token = auth.get_refresh_token()
            if not refresh_token:
                print("❌ 未配置refresh_token，无法自动刷新")
                print("\n建议操作:")
                print("  1. 在.env文件中添加 refresh_token 配置")
                print("  2. 或重新获取完整的B站登录信息")
                return False

            print("✅ 检测到refresh_token，可以尝试自动刷新")
            print(f"   Timestamp: {timestamp}")

        else:
            print("✅ Cookie状态正常，无需刷新")
            print(f"   Timestamp: {timestamp}")

    except Exception as e:
        print(f"❌ 检查过程出错: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 3. 测试实际API调用
    print("\n[3] 测试API调用...")
    try:
        from bilibili_api import user

        uid = BILIBILI_CONFIG.get("DedeUserID")
        if not uid:
            print("⚠️  未配置DedeUserID，跳过API测试")
            return True

        u = user.User(uid=int(uid), credential=credential)
        info = await u.get_user_info()

        if info:
            print("✅ API调用成功")
            print(f"   用户名: {info.get('name', 'N/A')}")
            print(f"   UID: {info.get('mid', 'N/A')}")
        else:
            print("⚠️  API调用返回空结果")

    except Exception as e:
        print(f"❌ API调用失败: {e}")
        print("\n可能的原因:")
        print("  1. 登录凭证已过期")
        print("  2. 网络问题")
        print("  3. API变更")
        return False

    # 4. 测试字幕获取功能
    print("\n[4] 测试字幕获取功能...")
    try:
        from services.ai_summary.subtitle_fetcher import (
            SubtitleErrorType,
            SubtitleFetcher,
        )

        test_video_url = "https://www.bilibili.com/video/BV1H4BHBZEWn"
        fetcher = SubtitleFetcher()

        print(f"   测试视频: {test_video_url}")
        subtitle_text = await fetcher.fetch_subtitle(test_video_url)

        if subtitle_text:
            lines = subtitle_text.split("\n")
            char_count = len(subtitle_text)
            print("✅ 字幕获取成功")
            print(f"   字幕行数: {len(lines)}")
            print(f"   字幕字数: {char_count}")
            print("   前3行预览:")
            for i, line in enumerate(lines[:3], 1):
                print(f"      {i}. {line[:60]}{'...' if len(line) > 60 else ''}")
        else:
            error_type = fetcher.last_error_type
            error_msg = fetcher.last_error or "未知错误"

            # 根据错误类型给出详细诊断
            print("❌ 字幕获取失败")
            print(f"   错误类型: {error_type.value}")
            print(f"   错误详情: {error_msg}")

            if error_type == SubtitleErrorType.COOKIE_EXPIRED:
                print("\n⚠️  诊断结果: Cookie已失效")
                print("   建议操作:")
                print("   1. 重新获取B站登录信息（参考 docs/BILIBILI_SETUP.md）")
                print("   2. 更新.env文件中的SESSDATA等配置")
                return False  # Cookie失效是严重问题
            elif error_type == SubtitleErrorType.CREDENTIAL_ERROR:
                print("\n⚠️  诊断结果: 凭证权限不足")
                print("   建议操作:")
                print("   1. 确认账号已登录")
                print("   2. 部分视频可能需要大会员权限")
            elif error_type == SubtitleErrorType.NO_SUBTITLE:
                print("\n📝 诊断结果: 视频本身没有字幕")
                print("   说明: 这不是登录问题，是视频本身未开启AI字幕或无语音内容")
            elif error_type == SubtitleErrorType.VIDEO_NOT_FOUND:
                print("\n📝 诊断结果: 视频不存在或已被删除")
            elif error_type == SubtitleErrorType.NETWORK_ERROR:
                print("\n⚠️  诊断结果: 网络连接问题")
                print("   建议操作: 检查网络连接")
            else:
                print("\n可能的原因:")
                print("  1. 该视频没有字幕")
                print("  2. 登录凭证权限不足")
                print("  3. 网络问题")
            # 字幕获取失败不影响整体认证状态（除非是Cookie失效）

    except Exception as e:
        print(f"❌ 字幕测试出错: {e}")
        import traceback

        traceback.print_exc()
        # 字幕测试失败不影响整体认证状态

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)

    return True


async def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.WARNING,  # 只显示警告及以上级别
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        success = await check_bilibili_auth()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n检查已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
