# -*- coding: utf-8 -*-
"""
AI视频总结服务模块

提供基于正规AI API的视频总结功能，使用B站字幕和AI大模型生成总结
"""

from .service import AISummaryService
from .subtitle_fetcher import SubtitleErrorType

__all__ = ["AISummaryService", "SubtitleErrorType"]
