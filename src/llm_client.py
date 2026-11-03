"""Small OpenAI-compatible chat client boundary."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import OpenAI


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall]


class ChatClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatResponse:
        """Return one model turn."""


class OpenAIChatClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY 未配置，真实模型运行需要 DeepSeek API Key。")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    @classmethod
    def from_env(cls) -> "OpenAIChatClient":
        load_dotenv()
        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
        )

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )
        message = response.choices[0].message
        return ChatResponse(
            content=message.content,
            tool_calls=[
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=call.function.arguments,
                )
                for call in (message.tool_calls or [])
            ],
        )

