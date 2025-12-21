# -*- coding: utf-8 -*-
"""
总结生成器模块

使用AI大模型和精心设计的提示词生成高质量的视频总结
"""

import logging
from typing import Optional

import tiktoken

from config import AI_CONFIG

from .ai_client import AIClient


class SummaryGenerator:
    """视频总结生成器"""

    # 系统提示词
    SYSTEM_PROMPT = """你是一个专业的视频内容总结助手，输出将直接放入 Markdown 区域。

通用要求：
1) 只输出 Markdown（不要输出 JSON/代码块/额外说明）。
2) 内容要可读、可扫描：用小标题与要点列表即可，不要追求“严格结构化”。
3) 优先提取“视频里真正说了什么”：观点、逻辑链、行动建议、风险提示。
4) 允许你做合理的推测/联想，并允许结合常识性外部知识辅助理解，但必须显式标注为【推测/联想】或【外部知识】；视频里明确表述的内容不需要额外标注。

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
- 当你在要点中加入“推测/联想”或“外部知识”时，在该条末尾标注【推测/联想】或【外部知识】。

## 时间线总结
- 请按字幕中出现的时间戳（形如“[00:59]”或“[01:02:03]”）把内容整理成 6-12 个时间段落。
- 每个段落格式参考：
    - 00:00 - 📌 段落主题：用 1 句概括该时间段核心内容
    - 下面用 2-4 个要点补充细节（不要写“思考/延伸/提问”）
- 时间点必须来自字幕里的时间戳，不要编造；若字幕缺少足够时间戳，则按内容顺序用“段落1/段落2…”替代。

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

        enc_name = AI_CONFIG.get("token_encoding")
        if not isinstance(enc_name, str) or not enc_name:
            raise ValueError("AI_TOKEN_ENCODING未配置")
        self._enc = tiktoken.get_encoding(enc_name)

        context_window_tokens = AI_CONFIG.get("context_window_tokens")
        if not isinstance(context_window_tokens, int) or context_window_tokens <= 0:
            raise ValueError("AI_CONTEXT_WINDOW_TOKENS必须是正整数")
        self._context_window_tokens = context_window_tokens

        max_output_tokens = AI_CONFIG.get("max_output_tokens")
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            raise ValueError("AI_MAX_OUTPUT_TOKENS必须是正整数")
        self._max_output_tokens = max_output_tokens

        map_max_output_tokens = AI_CONFIG.get("map_max_output_tokens")
        if not isinstance(map_max_output_tokens, int) or map_max_output_tokens <= 0:
            raise ValueError("AI_MAP_MAX_OUTPUT_TOKENS必须是正整数")
        self._map_max_output_tokens = map_max_output_tokens

    def _count_tokens(self, text: str) -> int:
        if not isinstance(text, str):
            raise ValueError("text必须是字符串")
        return len(self._enc.encode(text))

    def _count_tokens_for_messages(self, messages: list[dict]) -> int:
        if not isinstance(messages, list):
            raise ValueError("messages必须是list")

        # 参考 tiktoken 文档的 rough approximation；不同 provider 可能有细微差异
        num_tokens = 0
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("message必须是dict")
            num_tokens += 4
            for key, value in message.items():
                num_tokens += self._count_tokens(str(key))
                num_tokens += self._count_tokens(str(value))
        num_tokens += 2
        return num_tokens

    @staticmethod
    def _chunk_subtitle_by_lines(subtitle: str, max_chars: int) -> list[str]:
        if max_chars <= 0:
            raise ValueError("max_chars必须>0")
        if not isinstance(subtitle, str):
            raise ValueError("subtitle必须是字符串")

        lines = subtitle.splitlines()
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1
            if current and current_len + line_len > max_chars:
                chunks.append("\n".join(current))
                current = []
                current_len = 0

            # 单行超长时直接截断（避免死循环）
            if line_len > max_chars:
                chunks.append(line[: max_chars - 1])
                continue

            current.append(line)
            current_len += line_len

        if current:
            chunks.append("\n".join(current))

        return chunks

    def _chunk_subtitle_by_token_budget(
        self, subtitle: str, max_chunk_tokens: int
    ) -> list[str]:
        if max_chunk_tokens <= 0:
            raise ValueError("max_chunk_tokens必须>0")
        if not isinstance(subtitle, str):
            raise ValueError("subtitle必须是字符串")

        lines = subtitle.splitlines()
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for line in lines:
            # 每行都补一个换行 token 计入
            line_tokens = self._count_tokens(line + "\n")

            if current and current_tokens + line_tokens > max_chunk_tokens:
                chunks.append("\n".join(current))
                current = []
                current_tokens = 0

            # 极端情况下单行就超预算：直接按字符切片（字幕行通常不会到这里）
            if line_tokens > max_chunk_tokens:
                step = max(200, int(len(line) * (max_chunk_tokens / line_tokens)))
                start = 0
                while start < len(line):
                    part = line[start : start + step]
                    chunks.append(part)
                    start += step
                continue

            current.append(line)
            current_tokens += line_tokens

        if current:
            chunks.append("\n".join(current))

        return chunks

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

            # 先尝试“单次总结”：充分利用 DeepSeek 128K context
            direct_user_prompt = self.USER_PROMPT_TEMPLATE.format(subtitle=subtitle)
            direct_messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": direct_user_prompt},
            ]
            safety_margin = 1200
            direct_input_tokens = self._count_tokens_for_messages(direct_messages)

            fits_direct = (
                direct_input_tokens + self._max_output_tokens + safety_margin
                <= self._context_window_tokens
            )

            # 超长字幕分段总结兜底：map-reduce（chunk 要够大，避免过短影响效果）
            if not fits_direct:
                self.logger.warning(
                    "字幕超过上下文窗口，启用分段总结（token预算）"
                    f" input≈{direct_input_tokens}, ctx={self._context_window_tokens}, out={self._max_output_tokens}"
                )

                # 动态计算每个 chunk 的目标大小：基于 context window，避免 chunk 过短
                # 128K -> 约 21K tokens/chunk；上限 32K，下限 8K
                chunk_target_tokens = max(
                    8000, min(32000, self._context_window_tokens // 6)
                )

                map_prompt_prefix = (
                    "请总结下面这段【视频字幕片段】的关键信息，输出 Markdown 要点列表即可。\n"
                    "要求：\n"
                    "1) 只输出 Markdown；\n"
                    "2) 尽量保留片段中出现的原始时间戳（例如 [12:34] / [01:02:03]），不要编造时间点；\n"
                    "3) 只提炼片段里实际说了什么（观点、论据、结论、风险提示）。\n\n"
                )
                map_prompt_overhead = self._count_tokens(map_prompt_prefix) + 200
                map_chunk_budget = (
                    self._context_window_tokens
                    - self._map_max_output_tokens
                    - safety_margin
                    - map_prompt_overhead
                )
                if map_chunk_budget <= 0:
                    raise ValueError("map_chunk_budget计算结果<=0，请检查配置")

                chunk_budget = min(chunk_target_tokens, map_chunk_budget)
                chunks = self._chunk_subtitle_by_token_budget(
                    subtitle, max_chunk_tokens=chunk_budget
                )
                self.logger.info(
                    f"字幕将分为 {len(chunks)} 段进行摘要（chunk_tokens≈{chunk_budget}）"
                )

                chunk_summaries: list[str] = []
                for idx, chunk in enumerate(chunks):
                    chunk_prompt = map_prompt_prefix + (
                        f"【片段 {idx + 1}/{len(chunks)}】\n{chunk}\n\n片段要点："
                    )

                    messages = [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": chunk_prompt},
                    ]

                    part = await self.ai_client.chat_completion(
                        messages=messages,
                        temperature=0.5,
                        max_tokens=self._map_max_output_tokens,
                    )
                    if not part:
                        self.logger.error("分段总结失败：AI返回为空")
                        return None
                    chunk_summaries.append(part)

                subtitle = "\n\n".join(chunk_summaries)

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
                temperature=0.7,
                max_tokens=self._max_output_tokens,
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
