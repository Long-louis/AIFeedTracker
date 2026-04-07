# -*- coding: utf-8 -*-
"""
AI总结服务主模块

提供视频总结的统一入口和标准化接口
"""

import logging
from typing import Dict, List, Tuple

from config import AI_CONFIG, LOCAL_ASR_CONFIG

from .ai_client import AIClient
from .audio_transcription_service import AudioTranscriptionService
from .subtitle_fetcher import SubtitleErrorType, SubtitleFetcher
from .summary_generator import SummaryGenerator


class AISummaryService:
    """AI视频总结服务"""

    # 字幕获取重试配置
    SUBTITLE_RETRY_DELAYS = [60, 120, 180]  # 重试间隔（秒）：1分钟、2分钟、3分钟

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        user_data_dir: str = "./browser_data",
        chrome_path: str = None,
        feishu_bot=None,
    ):
        """
        初始化AI总结服务

        Args:
            headless: 兼容参数，实际不使用
            timeout: 兼容参数，实际不使用
            user_data_dir: 兼容参数，实际不使用
            chrome_path: 兼容参数，实际不使用
            feishu_bot: 飞书机器人实例（用于发送通知）
        """
        self.feishu_bot = feishu_bot
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 初始化子服务
        self.subtitle_fetcher = SubtitleFetcher()
        self.local_asr_enabled = bool(LOCAL_ASR_CONFIG.get("enabled"))
        self.audio_transcription_service = None
        if self.local_asr_enabled:
            self.audio_transcription_service = AudioTranscriptionService()

        # 初始化AI客户端
        try:
            api_key = AI_CONFIG.get("api_key")
            if not api_key:
                error_msg = "AI_API_KEY未配置，请在.env文件中设置"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            self.ai_client = AIClient(
                service=AI_CONFIG.get("service", "deepseek"),
                api_key=api_key,
                base_url=AI_CONFIG.get("base_url"),
                model=AI_CONFIG.get("model"),
            )

            self.summary_generator = SummaryGenerator(self.ai_client)

            self.logger.info("AI总结服务初始化成功")

        except Exception as e:
            self.logger.error(f"AI总结服务初始化失败: {e}")
            raise

    def _should_use_local_asr(self, error_type) -> bool:
        return self.local_asr_enabled and error_type == SubtitleErrorType.NO_SUBTITLE

    async def summarize_videos(
        self, video_urls: List[str]
    ) -> Tuple[bool, str, List[str], List[str]]:
        """
        总结视频的主要接口

        Args:
            video_urls: 视频URL列表

        Returns:
            Tuple[bool, str, List[str], List[str]]: (是否成功, 结果消息, 总结链接列表, 总结内容列表)
        """
        self.logger.info(f"开始总结 {len(video_urls)} 个视频")

        summary_links = []  # AI服务不生成链接，返回空列表
        summary_contents = []
        failed_videos = []

        try:
            for i, video_url in enumerate(video_urls):
                self.logger.info(
                    f"处理第 {i + 1}/{len(video_urls)} 个视频: {video_url}"
                )

                try:
                    # 1. 获取字幕
                    self.logger.info("步骤1: 获取字幕...")
                    subtitle = await self.subtitle_fetcher.fetch_subtitle(video_url)

                    if not subtitle:
                        error_type = self.subtitle_fetcher.last_error_type
                        detail = self.subtitle_fetcher.last_error

                        if self._should_use_local_asr(error_type):
                            self.logger.info("字幕缺失，进入本地ASR兜底: %s", video_url)
                            transcription_result = (
                                await self.audio_transcription_service.transcribe_video(
                                    video_url
                                )
                            )
                            if transcription_result:
                                subtitle = transcription_result["text"]
                                self.logger.info(
                                    "本地ASR转写成功，继续生成总结: %s", video_url
                                )
                            else:
                                error_msg = f"本地转写失败: {video_url}"
                                self.logger.error(error_msg)
                                failed_videos.append(video_url)
                                asr_detail = getattr(
                                    self.audio_transcription_service, "last_error", None
                                )
                                if asr_detail:
                                    summary_contents.append(
                                        f"❌ 本地转写失败: {asr_detail}"
                                    )
                                else:
                                    summary_contents.append("❌ 本地转写失败: 未知原因")
                                continue
                        else:
                            error_msg = f"获取字幕失败: {video_url}"
                            self.logger.error(error_msg)
                            failed_videos.append(video_url)

                            # 根据错误类型生成详细的失败原因
                            if error_type == SubtitleErrorType.COOKIE_EXPIRED:
                                summary_contents.append(f"❌ Cookie已失效: {detail}")
                            elif error_type == SubtitleErrorType.CREDENTIAL_ERROR:
                                summary_contents.append(f"❌ 凭证权限不足: {detail}")
                            elif error_type == SubtitleErrorType.NO_SUBTITLE:
                                summary_contents.append(f"❌ 视频无字幕: {detail}")
                            elif error_type == SubtitleErrorType.VIDEO_NOT_FOUND:
                                summary_contents.append(f"❌ 视频不存在: {detail}")
                            elif error_type == SubtitleErrorType.NETWORK_ERROR:
                                summary_contents.append(f"❌ 网络错误: {detail}")
                            elif detail:
                                summary_contents.append(f"❌ 获取字幕失败: {detail}")
                            else:
                                summary_contents.append("❌ 获取字幕失败: 未知原因")
                            continue

                    self.logger.info(f"字幕获取成功，长度: {len(subtitle)} 字符")

                    # 2. 生成总结
                    self.logger.info("步骤2: 生成AI总结...")
                    summary = await self.summary_generator.generate_summary(subtitle)

                    if not summary:
                        error_msg = f"生成总结失败: {video_url}"
                        self.logger.error(error_msg)
                        failed_videos.append(video_url)
                        detail = getattr(self.ai_client, "last_error", None)
                        if detail:
                            summary_contents.append(f"❌ AI总结生成失败: {detail}")
                        else:
                            summary_contents.append("❌ AI总结生成失败")
                        continue

                    self.logger.info(f"总结生成成功，长度: {len(summary)} 字符")

                    # 3. 添加到结果
                    summary_contents.append(summary)
                    self.logger.info(f"视频 {i + 1} 处理完成")

                except Exception as e:
                    error_msg = f"处理视频失败: {video_url}, 错误: {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    failed_videos.append(video_url)
                    summary_contents.append(f"❌ 处理失败: {str(e)}")

            # 4. 生成结果消息
            success_count = len(video_urls) - len(failed_videos)
            if success_count > 0:
                if len(failed_videos) == 0:
                    result_message = f"成功总结 {success_count} 个视频"
                    self.logger.info(result_message)
                    return True, result_message, summary_links, summary_contents
                else:
                    result_message = (
                        f"部分成功：总结了 {success_count}/{len(video_urls)} 个视频"
                    )
                    self.logger.warning(result_message)
                    # 发送部分失败通知
                    if self.feishu_bot and failed_videos:
                        try:
                            await self.feishu_bot.send_system_notification(
                                self.feishu_bot.LEVEL_WARNING,
                                "AI总结部分失败",
                                f"成功: {success_count}个\n失败: {len(failed_videos)}个\n\n失败的视频:\n"
                                + "\n".join(failed_videos),
                            )
                        except Exception:
                            pass
                    return True, result_message, summary_links, summary_contents
            else:
                error_msg = "所有视频总结都失败"
                self.logger.error(error_msg)
                # 发送全部失败通知
                if self.feishu_bot:
                    try:
                        details = []
                        for idx, url in enumerate(failed_videos):
                            reason = (
                                summary_contents[idx]
                                if idx < len(summary_contents)
                                else ""
                            )
                            details.append(f"{url}\n{reason}".strip())
                        await self.feishu_bot.send_system_notification(
                            self.feishu_bot.LEVEL_ERROR,
                            "AI总结服务失败",
                            f"{error_msg}\n\n失败详情:\n" + "\n\n".join(details),
                        )
                    except Exception:
                        pass
                return False, error_msg, summary_links, summary_contents

        except Exception as e:
            error_msg = f"视频总结过程异常: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            # 发送异常通知
            if self.feishu_bot:
                try:
                    await self.feishu_bot.send_system_notification(
                        self.feishu_bot.LEVEL_ERROR,
                        "AI总结服务异常",
                        f"{error_msg}\n\n视频数量: {len(video_urls)}",
                    )
                except Exception:
                    pass
            return False, error_msg, [], []

    async def get_service_statistics(self) -> Dict:
        """
        获取服务统计信息

        Returns:
            服务统计信息字典
        """
        return {
            "service": "AI Summary Service",
            "ai_service": AI_CONFIG.get("service", "deepseek"),
            "model": self.ai_client.model if hasattr(self, "ai_client") else "unknown",
            "status": "ready",
        }
