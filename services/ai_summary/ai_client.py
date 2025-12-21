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
    ):
        """
        初始化AI客户端

        Args:
            service: 服务名称（deepseek, zhipu, qwen）
            api_key: API密钥
            base_url: API地址（可选，不设置则使用默认值）
            model: 模型名称（可选，不设置则使用默认值）
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

        # 创建OpenAI客户端
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
        )

        self.logger.info(
            f"AI客户端初始化成功: service={self.service}, base_url={self.base_url}, model={self.model}"
        )

        # 记录最近一次调用失败原因，便于上层展示（例如推送到飞书）
        self.last_error: Optional[str] = None

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
        try:
            self.logger.debug(
                f"调用AI服务: model={self.model}, messages={len(messages)}条"
            )

            # 调用API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 提取返回内容
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
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
