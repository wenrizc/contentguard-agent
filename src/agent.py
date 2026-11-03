"""Model-driven ReAct runner for ContentGuard."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .catalog import DataCatalog
from .guardrails import Guardrails
from .llm_client import ChatClient, ChatResponse, ToolCall
from .schemas import DraftInput, ReviewResult, TaskInput
from .storage import DraftStore
from .tools.material import MaterialTool
from .tools.review import ReviewTool
from .tools.schedule import ScheduleTool
from .moderation.mock import MockVideoModerator


SYSTEM_PROMPT = """你是 ContentGuard Agent，负责小影短视频素材审核和排期草稿。
你必须根据工具返回的结构化证据决定下一步，每次只调用一个工具，然后观察结果再行动。
工具选择由你决定，不能假设未查询到的事实。审核未通过、资料缺失、审核服务错误或字段不完整时不能保存。
指定时段冲突时，硬性发布时间不能擅自修改；候选时间只能作为建议，只有用户显式确认后才能保存。
save_draft 只保存草稿，不代表已经发布。只有工具返回 save_status=SAVED 后才能用 finish 的 COMPLETED。
需要人工确认时用 NEEDS_CONFIRMATION，并提供 suggested_start；风险不可接受时用 BLOCKED。
每次工具参数中的 decision_basis 写一句简短的业务依据，不要输出隐藏思维过程。
"""


def _string_property(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


DECISION_BASIS = _string_property("一句简短的业务依据，不包含隐藏思维过程")

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_material",
            "description": "读取素材元数据、字幕和版权授权资料。",
            "parameters": {
                "type": "object",
                "properties": {"material_id": _string_property("素材 ID"), "decision_basis": DECISION_BASIS},
                "required": ["material_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_rules",
            "description": "检查版权、字幕规则、品牌规则和 Mock 视频审核结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "material_id": _string_property("素材 ID"),
                    "platform": _string_property("目标平台"),
                    "decision_basis": DECISION_BASIS,
                },
                "required": ["material_id", "platform"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_slot",
            "description": "检查指定账号和时间区间是否冲突。",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": _string_property("账号 ID"),
                    "start": _string_property("带时区 ISO 8601 开始时间"),
                    "duration_minutes": {"type": "integer", "minimum": 1},
                    "decision_basis": DECISION_BASIS,
                },
                "required": ["account_id", "start", "duration_minutes"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_slots",
            "description": "查找可供用户确认的候选时段，不会自动占用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": _string_property("账号 ID"),
                    "requested_start": _string_property("带时区 ISO 8601 起始时间"),
                    "duration_minutes": {"type": "integer", "minimum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 5},
                    "decision_basis": DECISION_BASIS,
                },
                "required": ["account_id", "requested_start", "duration_minutes"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_draft",
            "description": "在审核通过、确认状态满足且时段事务复核通过后保存排期草稿。",
            "parameters": {
                "type": "object",
                "properties": {
                    "material_id": _string_property("素材 ID"),
                    "start": _string_property("带时区 ISO 8601 保存时间"),
                    "confirmation_status": {
                        "type": "string",
                        "enum": ["PENDING", "CONFIRMED", "NOT_REQUIRED"],
                    },
                    "decision_basis": DECISION_BASIS,
                },
                "required": ["material_id", "start", "confirmation_status"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "用结构化状态结束当前任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_status": {
                        "type": "string",
                        "enum": ["COMPLETED", "NEEDS_CONFIRMATION", "BLOCKED", "INCOMPLETE"],
                    },
                    "reason": _string_property("面向运营人员的简短结论和依据"),
                    "suggested_start": _string_property("待确认的带时区 ISO 8601 候选时间"),
                    "confirmation_status": {
                        "type": "string",
                        "enum": ["PENDING", "CONFIRMED", "NOT_REQUIRED"],
                    },
                },
                "required": ["task_status", "reason"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_basis: str | None = None


class MaterialArgs(ToolArgs):
    material_id: str


class ReviewArgs(ToolArgs):
    material_id: str
    platform: str


class SlotArgs(ToolArgs):
    account_id: str
    start: datetime
    duration_minutes: int = Field(gt=0)


class FindSlotArgs(ToolArgs):
    account_id: str
    requested_start: datetime
    duration_minutes: int = Field(gt=0)
    limit: int = Field(default=3, ge=1, le=5)


class SaveArgs(ToolArgs):
    material_id: str
    start: datetime
    confirmation_status: Literal["PENDING", "CONFIRMED", "NOT_REQUIRED"]


class FinishArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_status: Literal["COMPLETED", "NEEDS_CONFIRMATION", "BLOCKED", "INCOMPLETE"]
    reason: str
    suggested_start: datetime | None = None
    confirmation_status: Literal["PENDING", "CONFIRMED", "NOT_REQUIRED"] | None = None


@dataclass
class AgentState:
    confirmed_start: datetime | None = None
    materials: dict[str, dict] = field(default_factory=dict)
    reviews: dict[str, ReviewResult] = field(default_factory=dict)
    saves: dict[str, dict] = field(default_factory=dict)
    proposed_starts: dict[str, str] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentDependencies:
    material_tool: MaterialTool
    review_tool: ReviewTool
    schedule_tool: ScheduleTool
    draft_store: DraftStore
    guardrails: Guardrails


def build_dependencies(catalog: DataCatalog, database_path) -> AgentDependencies:
    return AgentDependencies(
        material_tool=MaterialTool(catalog),
        review_tool=ReviewTool(catalog, MockVideoModerator(catalog)),
        schedule_tool=ScheduleTool(catalog),
        draft_store=DraftStore(database_path, catalog.schedule_slots),
        guardrails=Guardrails(),
    )


class AgentRunner:
    def __init__(self, client: ChatClient, dependencies: AgentDependencies, max_tool_calls: int = 10) -> None:
        self.client = client
        self.dependencies = dependencies
        self.max_tool_calls = max_tool_calls

    def run(self, task: TaskInput, confirmed_start: datetime | None = None) -> dict[str, Any]:
        state = AgentState(confirmed_start=confirmed_start)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": task.model_dump(mode="json"),
                        "user_confirmed_start": confirmed_start.isoformat() if confirmed_start else None,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        calls = 0
        while calls < self.max_tool_calls:
            try:
                response = self.client.complete(messages, TOOLS)
            except Exception as exc:  # provider boundary: preserve failure state
                return self._incomplete(state, "MODEL_ERROR", f"模型调用失败：{type(exc).__name__}: {exc}", calls)

            if not response.tool_calls:
                return self._incomplete(state, "MODEL_DID_NOT_SELECT_TOOL", "模型没有选择结构化工具动作。", calls)

            messages.append(self._assistant_message(response))
            if len(response.tool_calls) != 1:
                remaining = self.max_tool_calls - calls
                for call in response.tool_calls[:remaining]:
                    calls += 1
                    result = {
                        "status": "INVALID_TOOL_TURN",
                        "reason_code": "ONE_TOOL_PER_TURN",
                        "reason": "每轮只能选择一个工具；请根据上一次结果重新选择。",
                    }
                    self._record(state, call, result, calls)
                    messages.append(self._tool_message(call, result))
                if len(response.tool_calls) > remaining:
                    return self._incomplete(
                        state,
                        "MAX_TOOL_CALLS",
                        f"已达到工具调用上限 {self.max_tool_calls}，任务未完成。",
                        calls,
                    )
                continue

            call = response.tool_calls[0]
            calls += 1
            result, finish = self._dispatch(call, task, state)
            self._record(state, call, result, calls)
            if finish is not None:
                if finish["status"] == "RETRY":
                    messages.append(self._tool_message(call, finish))
                    continue
                return self._finalize(finish, task, state, calls)
            messages.append(self._tool_message(call, result))

        return self._incomplete(state, "MAX_TOOL_CALLS", f"已达到工具调用上限 {self.max_tool_calls}，任务未完成。", calls)

    def _dispatch(self, call: ToolCall, task: TaskInput, state: AgentState) -> tuple[dict, dict | None]:
        try:
            arguments = json.loads(call.arguments)
            if call.name == "get_material":
                args = MaterialArgs.model_validate(arguments)
                result = self.dependencies.material_tool.get_material(args.material_id)
                state.materials[args.material_id] = result
                return result, None
            if call.name == "check_rules":
                args = ReviewArgs.model_validate(arguments)
                result = self.dependencies.review_tool.check_rules(args.material_id, args.platform)
                state.reviews[args.material_id] = ReviewResult.model_validate(result)
                return result, None
            if call.name == "check_slot":
                args = SlotArgs.model_validate(arguments)
                if args.start.tzinfo is None:
                    return self._invalid("TIMEZONE_REQUIRED", "start 必须包含时区。"), None
                return self.dependencies.schedule_tool.check_slot(args.account_id, args.start, args.duration_minutes), None
            if call.name == "find_slots":
                args = FindSlotArgs.model_validate(arguments)
                if args.requested_start.tzinfo is None:
                    return self._invalid("TIMEZONE_REQUIRED", "requested_start 必须包含时区。"), None
                return self.dependencies.schedule_tool.find_slots(
                    args.account_id, args.requested_start, args.duration_minutes, args.limit
                ), None
            if call.name == "save_draft":
                return self._save(
                    args=SaveArgs.model_validate(arguments),
                    task=task,
                    state=state,
                ), None
            if call.name == "finish":
                finish = self._finish(FinishArgs.model_validate(arguments), task, state)
                return {"status": "FINISH_SELECTED", **finish}, finish
            return self._invalid("UNKNOWN_TOOL", f"未注册工具：{call.name}"), None
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            return self._invalid("INVALID_ARGUMENTS", str(exc)), None

    def _save(self, args: SaveArgs, task: TaskInput, state: AgentState) -> dict:
        if args.material_id not in task.material_ids:
            return self._invalid("MATERIAL_NOT_IN_TASK", "待保存素材必须属于当前任务的 material_ids。")
        review = state.reviews.get(args.material_id)
        if review is None:
            return self._invalid("REVIEW_REQUIRED", "保存前必须先取得该素材的 check_rules 结果。")
        permission = self.dependencies.guardrails.validate_save(
            task,
            args.material_id,
            review,
            args.start,
            args.confirmation_status,
            confirmed_start=state.confirmed_start,
        )
        if not permission["allowed"]:
            return {
                "save_status": "FAILED",
                "reason_code": permission["reason_code"],
                "reason": permission["reason"],
                "guardrail": permission,
            }
        draft = DraftInput(
            source_request_id=task.source_request_id,
            material_id=args.material_id,
            account_id=task.account_id,
            platform=task.platform,
            start=args.start,
            duration_minutes=task.duration_minutes,
            review_status=review.review_status,
            confirmation_status=args.confirmation_status,
            evidence={"review": review.model_dump(mode="json")},
        )
        result = self.dependencies.draft_store.save_draft(draft)
        state.saves[args.material_id] = result
        state.proposed_starts[args.material_id] = args.start.isoformat()
        return result

    def _finish(self, args: FinishArgs, task: TaskInput, state: AgentState) -> dict:
        if args.task_status == "COMPLETED":
            missing = [material_id for material_id in task.material_ids if state.saves.get(material_id, {}).get("save_status") != "SAVED"]
            if missing:
                return {
                    "status": "RETRY",
                    "reason_code": "FINISH_REQUIRES_SAVED_DRAFT",
                    "reason": f"COMPLETED 需要所有素材都有 save_status=SAVED，缺少：{missing}",
                }
        if args.task_status == "NEEDS_CONFIRMATION" and args.suggested_start is None:
            return {
                "status": "RETRY",
                "reason_code": "SUGGESTED_START_REQUIRED",
                "reason": "NEEDS_CONFIRMATION 必须提供 suggested_start。",
            }
        return {"status": "ACCEPTED", **args.model_dump(mode="json")}

    @staticmethod
    def _assistant_message(response: ChatResponse) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in response.tool_calls
            ],
        }

    @staticmethod
    def _tool_message(call: ToolCall, result: dict) -> dict[str, Any]:
        return {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)}

    @staticmethod
    def _invalid(code: str, reason: str) -> dict:
        return {"status": "INVALID", "reason_code": code, "reason": reason}

    @staticmethod
    def _record(state: AgentState, call: ToolCall, result: dict, calls: int) -> None:
        try:
            arguments = json.loads(call.arguments)
        except json.JSONDecodeError:
            arguments = {"raw": call.arguments}
        if state.trace:
            state.trace[-1]["next_action"] = call.name
        state.trace.append(
            {
                "step": len(state.trace) + 1,
                "tool": call.name,
                "parameters": arguments,
                "return_summary": result,
                "next_action": "END" if call.name == "finish" else "pending_model_decision",
                "decision_basis": arguments.get(
                    "decision_basis",
                    arguments.get("reason", "未提供；依据保留在结构化工具结果中"),
                ),
                "tool_call_count": calls,
            }
        )

    @staticmethod
    def _finalize(finish: dict, task: TaskInput, state: AgentState, calls: int) -> dict[str, Any]:
        review_status = "UNKNOWN"
        findings: list[dict] = []
        for material_id in task.material_ids:
            if material_id in state.reviews:
                review_status = state.reviews[material_id].review_status
                findings.extend(item.model_dump(mode="json") for item in state.reviews[material_id].findings)
        save_status = "NOT_ATTEMPTED"
        if any(item.get("save_status") == "SAVED" for item in state.saves.values()):
            save_status = "SAVED"
        elif any(item.get("save_status") == "FAILED" for item in state.saves.values()):
            save_status = "FAILED"
        confirmation_status = finish.get("confirmation_status")
        if confirmation_status is None:
            for saved in state.saves.values():
                draft = saved.get("draft") or {}
                if draft.get("confirmation_status"):
                    confirmation_status = draft["confirmation_status"]
                    break
        suggested_start = finish.get("suggested_start")
        if suggested_start is None and finish["task_status"] == "COMPLETED":
            suggested_start = next(iter(state.proposed_starts.values()), task.requested_start.isoformat())
        pending_items: list[str] = []
        if finish["task_status"] == "NEEDS_CONFIRMATION":
            pending_items.append("用户确认建议时段")
        if review_status == "PENDING":
            pending_items.append("补充审核所需资料")
        return {
            "task_status": finish["task_status"],
            "reason": finish["reason"],
            "review_status": review_status,
            "risk_reasons": findings,
            "suggested_start": suggested_start,
            "confirmation_status": confirmation_status,
            "pending_items": pending_items,
            "save_status": save_status,
            "trace": state.trace,
            "tool_call_count": calls,
        }

    @staticmethod
    def _incomplete(state: AgentState, code: str, reason: str, calls: int) -> dict[str, Any]:
        save_status = "NOT_ATTEMPTED"
        if any(item.get("save_status") == "SAVED" for item in state.saves.values()):
            save_status = "SAVED"
        elif any(item.get("save_status") == "FAILED" for item in state.saves.values()):
            save_status = "FAILED"
        return {
            "task_status": "INCOMPLETE",
            "reason": reason,
            "reason_code": code,
            "review_status": "UNKNOWN",
            "risk_reasons": [],
            "suggested_start": None,
            "confirmation_status": None,
            "pending_items": [],
            "save_status": save_status,
            "trace": state.trace,
            "tool_call_count": calls,
        }

