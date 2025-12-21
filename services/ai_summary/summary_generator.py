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
    SYSTEM_PROMPT = """你是一个专业的视频内容总结助手，输出将直接放入 Markdown 区域。

通用要求：
1) 只输出 Markdown（不要输出 JSON/代码块/额外说明）。
2) 内容要可读、可扫描：用小标题与要点列表即可，不要追求“严格结构化”。
3) 优先提取“视频里真正说了什么”：观点、逻辑链、行动建议、风险提示。
4) 允许你做合理的推测/联想，并允许结合常识性外部知识辅助理解，但必须显式标注为【推测/联想】或【外部知识】；视频明确表述的内容标注为【视频原文】。

财经类优先级（当字幕明显是财经/投资话题时）：
- 重点抓取具体标的（股票/ETF/指数/行业/加密资产/商品等），以及博主对它们的态度（看多/看空/观望）与理由。
- 如果字幕中出现公司名但没出现代码，不要强行编造代码；可以在【推测/联想】里给出“可能对应的标的/代码候选”，但要明确是不确定的。
"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """请把下面的视频字幕整理成一段发送给用户进行阅读的视频内容总结。

写作目标：
- 让读者看懂“博主讲了什么、为什么、对哪些标的有何观点、风险是什么”。
- 请用 Markdown 小标题 + 要点列表提升可读性。

建议的写法（可按内容增删，不要机械套模板）：

## 一句话总结
用 1-2 句写清主线。

## 关键信息/观点
- 用 6-12 条要点列出核心观点与逻辑。
- 每条末尾用标签标注来源：
    - 【视频原文】字幕里明确说到的
    - 【推测/联想】你基于上下文的合理推断
    - 【外部知识】你引用常识性背景来解释（不要太长）

## 涉及的标的（若有，财经视频务必优先列出）
- 逐条列出“公司/标的名称 +（若字幕里出现则写）代码/市场 + 博主态度 + 主要理由”。
- 如果字幕没给代码：代码写“未提及”；允许在【推测/联想】里给候选，但必须标注不确定。

## 风险与不确定性
- 列出博主提到或你从其逻辑中识别出的关键风险点（用【视频原文】/【推测/联想】标注）。

## 可执行的关注清单（可选）
- 给出 3-6 条“接下来该关注什么”的清单（例如：财报要点/政策节点/行业数据/价格行为/公告）。

视频字幕：
{subtitle}
"""

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
