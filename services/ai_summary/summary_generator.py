# -*- coding: utf-8 -*-
"""
总结生成器模块

使用AI大模型和精心设计的提示词生成高质量的视频总结
"""

import logging
from typing import Optional

from .ai_client import AIClient


class SummaryGenerator:
    """视频总结生成器"""

    # 系统提示词
    SYSTEM_PROMPT = """你是一个专业的视频内容总结助手，擅长从视频字幕中提取关键信息并生成精美的结构化总结。

你的总结需要：
1. 准确提取视频的核心观点和关键信息
2. 使用清晰的Markdown格式组织内容
3. 保持客观，不添加字幕中没有的内容
4. 语言简洁流畅，重点突出
5. 生成有深度的思考问题引发读者思考"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """请根据以下视频字幕内容，生成一份高质量的结构化总结，格式要求如下：

## 📋 格式要求

### 1. 摘要（必需）
用一段话（100-200字）概括视频的核心内容和主要价值。

### 2. 亮点（必需）
- 使用无序列表（- 💡）列出6-8个关键要点
- 每个要点一句话，简洁明确
- 使用emoji图标（💡 📈 📉 🔄 🎯 📊 等）增强可读性

### 3. 标签（必需）
使用 #标签名 格式，提取3-5个关键主题标签

### 4. 思考（必需）
提出2-3个引发深度思考的问题，格式：
1. 问题内容...
2. 问题内容...

### 5. 视频章节总结（如果能识别出明显的章节结构）
使用三级标题（###）划分章节，每个章节包含：
- 章节标题（包含emoji图标）
- 该部分的核心内容总结（2-3句话）

## 📝 输出格式示例

## 摘要
（用一段话概括视频核心内容和价值）

### 亮点
- 💡 要点1：内容...
- 📈 要点2：内容...
- 📉 要点3：内容...
- 🔄 要点4：内容...
- 🎯 要点5：内容...
- 📊 要点6：内容...

#标签1 #标签2 #标签3

### 思考
1. 思考问题1...
2. 思考问题2...

## 视频章节总结

### 🤔 章节1标题
章节1的核心内容总结...

### 📈 章节2标题
章节2的核心内容总结...

### 💡 章节3标题
章节3的核心内容总结...

## ⚠️ 注意事项
- 保持客观，只提取字幕中的信息
- 语言简洁流畅，便于阅读
- 如果字幕内容不够丰富，可以适当减少章节数量
- 标签要准确反映视频主题
- 思考问题要有深度，能引发进一步的思考

**视频字幕内容：**
{subtitle}

请开始总结："""

    def __init__(self, ai_client: AIClient):
        """
        初始化总结生成器

        Args:
            ai_client: AI客户端实例
        """
        self.ai_client = ai_client
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def generate_summary(self, subtitle: str) -> Optional[str]:
        """
        生成视频总结

        Args:
            subtitle: 视频字幕文本

        Returns:
            Markdown格式的总结内容，失败返回None
        """
        try:
            if not subtitle or len(subtitle.strip()) < 50:
                self.logger.error("字幕内容太短，无法生成总结")
                return None

            self.logger.info(f"开始生成总结，字幕长度: {len(subtitle)} 字符")

            # 如果字幕太长，需要截断（防止超过token限制）
            max_subtitle_length = 30000  # 约10000个token
            if len(subtitle) > max_subtitle_length:
                self.logger.warning(
                    f"字幕过长（{len(subtitle)}字符），将截断到{max_subtitle_length}字符"
                )
                subtitle = (
                    subtitle[:max_subtitle_length] + "...\n[字幕因长度限制已截断]"
                )

            # 构建提示词
            user_prompt = self.USER_PROMPT_TEMPLATE.format(subtitle=subtitle)

            # 构建消息
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            # 调用AI
            summary = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.7,  # 适中的创造性
                max_tokens=3000,  # 增加输出长度以支持更详细的总结
            )

            if summary:
                self.logger.info(f"总结生成成功，长度: {len(summary)} 字符")
                return summary
            else:
                self.logger.error("AI返回的总结为空")
                return None

        except Exception as e:
            self.logger.error(f"生成总结失败: {e}", exc_info=True)
            return None

    async def generate_short_summary(self, subtitle: str) -> Optional[str]:
        """
        生成简短总结（用于快速预览）

        Args:
            subtitle: 视频字幕文本

        Returns:
            简短总结（100-200字），失败返回None
        """
        try:
            if not subtitle or len(subtitle.strip()) < 50:
                self.logger.error("字幕内容太短，无法生成总结")
                return None

            # 简短总结的提示词
            short_prompt = f"""请用一段话（100-200字）总结以下视频的核心内容：

{subtitle[:5000]}

总结："""

            messages = [
                {"role": "system", "content": "你是一个专业的内容总结助手。"},
                {"role": "user", "content": short_prompt},
            ]

            summary = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=300,
            )

            return summary

        except Exception as e:
            self.logger.error(f"生成简短总结失败: {e}")
            return None
