# -*- coding: utf-8 -*-
"""
AI客户端模块

统一封装对各种AI服务的调用（DeepSeek、智谱AI、通义千问等）
"""

import logging
from typing import Optional

from openai import AsyncOpenAI


class AIClient:
    """统一的AI服务客户端，支持多个国内AI服务"""

    # 各服务的默认配置
    SERVICE_CONFIGS = {
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
        },
        "zhipu": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4/",
            "model": "glm-4",
        },
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-turbo",
        },
    }

    def __init__(
        self,
        service: str = "deepseek",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ):
        """
        初始化AI客户端

        Args:
            service: 服务名称（deepseek, zhipu, qwen）
            api_key: API密钥
            base_url: API地址（可选，不设置则使用默认值）
            model: 模型名称（可选，不设置则使用默认值）
            reasoning_effort: 推理强度（low/high/max），仅对推理模型生效。
                视频总结用 low 即可，省 token 又避免 content 为空。
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        if not api_key:
            raise ValueError("API Key不能为空，请在.env文件中配置AI_API_KEY")

        self.service = service.lower()

        # 获取配置
        config = self.SERVICE_CONFIGS.get(
            self.service, self.SERVICE_CONFIGS["deepseek"]
        )

        # 使用提供的配置或默认配置
        self.base_url = base_url or config["base_url"]
        self.model = model or config["model"]
        self.reasoning_effort = reasoning_effort

        # 创建OpenAI客户端
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
        )

        self.logger.info(
            f"AI客户端初始化成功: service={self.service}, base_url={self.base_url}, "
            f"model={self.model}, reasoning_effort={self.reasoning_effort}"
        )

        # 记录最近一次调用失败原因，便于上层展示（例如推送到飞书）
        self.last_error: Optional[str] = None

    @staticmethod
    def _extract_reasoning_content(choice: object) -> Optional[str]:
        """从 OpenAI SDK 响应中提取 reasoning_content（推理模型字段）。

        OpenAI SDK v2.x 的 ChatCompletionMessage 不含 reasoning_content
        字段定义，但 pydantic 模型允许通过 __pydantic_extra__ 或
        model_extra 访问未知字段。这里做多层兜底提取。
        """
        msg = choice.message
        # pydantic v2: model_extra
        extra = getattr(msg, "model_extra", None) or getattr(msg, "__pydantic_extra__", None)
        if extra and isinstance(extra, dict):
            rc = extra.get("reasoning_content")
            if rc:
                return rc
        # 最后兜底：直接访问属性（某些 SDK 版本会透传）
        rc = getattr(msg, "reasoning_content", None)
        if rc:
            return rc
        return None

    async def chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        调用AI进行对话补全

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数（0-1），越高越随机
            max_tokens: 最大生成token数

        Returns:
            AI生成的文本，失败返回None
        """
        for attempt in range(2):  # 最多重试1次
            try:
                self.logger.debug(
                    f"调用AI服务: model={self.model}, messages={len(messages)}条"
                    f"{f', attempt={attempt+1}' if attempt > 0 else ''}"
                )

                effective_max_tokens = max_tokens
                if attempt == 1 and max_tokens:
                    # 重试时翻倍 max_tokens，给 reasoning 更多预算
                    effective_max_tokens = max_tokens * 2
                    self.logger.warning(
                        f"AI返回空内容，重试中(max_tokens {max_tokens} -> {effective_max_tokens})"
                    )

                # 调用API
                kwargs = dict(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=effective_max_tokens,
                )
                if self.reasoning_effort:
                    # DeepSeek V4 推理模型：设置 reasoning_effort + thinking
                    # 官方文档：https://api-docs.deepseek.com/guides/thinking_mode
                    kwargs["reasoning_effort"] = self.reasoning_effort
                    kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

                response = await self.client.chat.completions.create(**kwargs)

                # 提取返回内容
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    content = choice.message.content

                    if not content:
                        # reasoning_content 兜底：推理模型可能把所有 token
                        # 都花在 reasoning 上，content 返回 null
                        reasoning = self._extract_reasoning_content(choice)
                        if reasoning:
                            self.logger.warning(
                                f"AI content 为空，使用 reasoning_content 兜底"
                                f"(长度: {len(reasoning)} 字符)"
                            )
                            content = reasoning
                        elif attempt == 0:
                            # 第一次为空且有 reasoning_content 兜底也失败 → 重试
                            self.logger.warning(
                                f"AI content 和 reasoning_content 均为空"
                                f"(finish_reason={choice.finish_reason})"
                            )
                            continue  # 进入第二次循环重试

                    self.last_error = None
                    self.logger.info(
                        f"AI响应成功，长度: {len(content) if content else 0} 字符"
                    )
                    return content
                else:
                    self.last_error = "AI响应为空"
                    self.logger.error(self.last_error)
                    return None

            except Exception as e:
                self.last_error = str(e)
                self.logger.error(f"调用AI服务失败: {e}", exc_info=True)
                if attempt == 0:
                    continue  # 重试一次
                return None

        self.last_error = "AI返回内容为空(已重试)"
        self.logger.error(self.last_error)
        return None

    async def summarize_text(
        self,
        text: str,
        system_prompt: str = "你是一个专业的视频内容总结助手。",
        user_prompt_template: Optional[str] = None,
    ) -> Optional[str]:
        """
        使用AI总结文本

        Args:
            text: 要总结的文本
            system_prompt: 系统提示词
            user_prompt_template: 用户提示词模板，{text}会被替换为实际文本

        Returns:
            总结内容，失败返回None
        """
        try:
            # 如果没有提供用户提示词模板，使用默认的
            if not user_prompt_template:
                user_prompt_template = "请总结以下内容：\n\n{text}"

            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt_template.format(text=text)},
            ]

            # 调用AI
            return await self.chat_completion(messages, temperature=0.7)

        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"文本总结失败: {e}")
            return None
