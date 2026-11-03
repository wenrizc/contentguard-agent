"""Offline protocol client for flow verification.

This is deliberately a small result-driven fake. It is useful for replaying
the tool protocol without credentials, but it is not evidence of LLM quality.
"""

from __future__ import annotations

import json
from typing import Any

from .llm_client import ChatResponse, ToolCall


class OfflineScenarioClient:
    mode = "offline_mock"

    def __init__(self) -> None:
        self._call_number = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatResponse:
        self._call_number += 1
        task_payload = json.loads(messages[1]["content"])
        task = task_payload["task"]
        confirmed_start = task_payload.get("user_confirmed_start")
        material_id = task["material_ids"][0]
        previous_name, previous_result = self._previous_tool(messages)

        if previous_name is None:
            return self._call("get_material", {"material_id": material_id, "decision_basis": "读取素材证据"})
        if previous_name == "get_material":
            return self._call(
                "check_rules",
                {
                    "material_id": material_id,
                    "platform": task["platform"],
                    "decision_basis": "根据素材资料检查审核规则",
                },
            )
        if previous_name == "check_rules":
            if previous_result.get("review_status") != "PASSED":
                return self._call(
                    "finish",
                    {
                        "task_status": "BLOCKED",
                        "reason": "审核结果未通过，需补充资料或处理风险。",
                    },
                )
            start = confirmed_start or task["requested_start"]
            return self._call(
                "check_slot",
                {
                    "account_id": task["account_id"],
                    "start": start,
                    "duration_minutes": task["duration_minutes"],
                    "decision_basis": "审核通过后检查目标时段",
                },
            )
        if previous_name == "check_slot":
            if previous_result.get("available"):
                return self._call(
                    "save_draft",
                    {
                        "material_id": material_id,
                        "start": confirmed_start or task["requested_start"],
                        "confirmation_status": "CONFIRMED" if confirmed_start else "NOT_REQUIRED",
                        "decision_basis": "时段可用，保存排期草稿",
                    },
                )
            return self._call(
                "find_slots",
                {
                    "account_id": task["account_id"],
                    "requested_start": task["requested_start"],
                    "duration_minutes": task["duration_minutes"],
                    "decision_basis": "目标时段冲突，查询可确认候选",
                },
            )
        if previous_name == "find_slots":
            candidates = previous_result.get("candidates", [])
            if candidates:
                return self._call(
                    "finish",
                    {
                        "task_status": "NEEDS_CONFIRMATION",
                        "reason": "目标时段已占用，候选时段需用户确认。",
                        "suggested_start": candidates[0]["start"],
                        "confirmation_status": "PENDING",
                    },
                )
            return self._call("finish", {"task_status": "BLOCKED", "reason": "没有可用候选时段。"})
        if previous_name == "save_draft":
            if previous_result.get("save_status") == "SAVED":
                return self._call("finish", {"task_status": "COMPLETED", "reason": "审核通过并保存排期草稿。"})
            return self._call("finish", {"task_status": "BLOCKED", "reason": "排期草稿保存失败。"})
        return self._call("finish", {"task_status": "INCOMPLETE", "reason": "离线场景无法继续。"})

    def _previous_tool(self, messages: list[dict[str, Any]]) -> tuple[str | None, dict]:
        tool_message = next((message for message in reversed(messages) if message.get("role") == "tool"), None)
        assistant_message = next((message for message in reversed(messages) if message.get("role") == "assistant"), None)
        if not tool_message or not assistant_message:
            return None, {}
        calls = assistant_message.get("tool_calls", [])
        if not calls:
            return None, {}
        result = json.loads(tool_message.get("content", "{}"))
        return calls[0]["function"]["name"], result

    def _call(self, name: str, arguments: dict[str, Any]) -> ChatResponse:
        return ChatResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id=f"offline-call-{self._call_number}",
                    name=name,
                    arguments=json.dumps(arguments, ensure_ascii=False),
                )
            ],
        )

