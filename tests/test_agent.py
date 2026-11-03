from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.agent import AgentRunner, build_dependencies
from src.catalog import DataCatalog
from src.llm_client import ChatResponse, ToolCall
from src.offline import OfflineScenarioClient
from src.schemas import TaskInput


ROOT = Path(__file__).parents[1]


class ScriptedClient:
    """A deterministic provider double for protocol tests only."""

    def __init__(self, turns: list[tuple[str, dict]]) -> None:
        self.turns = list(turns)
        self.seen_messages: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        self.seen_messages.append(messages)
        name, arguments = self.turns.pop(0)
        return ChatResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id=f"call-{len(self.seen_messages)}",
                    name=name,
                    arguments=json.dumps(arguments, ensure_ascii=False),
                )
            ],
        )


class MultiCallThenScriptedClient:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        self.calls += 1
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall("call-a", "get_material", json.dumps({"material_id": "M01"})),
                    ToolCall("call-b", "check_rules", json.dumps({"material_id": "M01", "platform": "douyin"})),
                ],
            )
        return ChatResponse(
            content=None,
            tool_calls=[ToolCall("call-c", "finish", json.dumps({"task_status": "BLOCKED", "reason": "测试结束"}))],
        )


def task(material_id: str, requested_start: str, hard_time: bool = False) -> TaskInput:
    return TaskInput(
        source_request_id=f"REQ-AGENT-{material_id}",
        material_ids=[material_id],
        account_id="official_cn",
        platform="douyin",
        requested_start=datetime.fromisoformat(requested_start),
        duration_minutes=30,
        hard_time=hard_time,
        conflict_policy="ask_before_change",
    )


def runner(client: ScriptedClient, tmp_path: Path) -> AgentRunner:
    catalog = DataCatalog(ROOT / "data")
    return AgentRunner(client, build_dependencies(catalog, tmp_path / "drafts.sqlite"))


def test_react_path_changes_to_candidate_and_requests_confirmation(tmp_path: Path) -> None:
    client = ScriptedClient(
        [
            ("get_material", {"material_id": "M01", "decision_basis": "先读取素材证据"}),
            ("check_rules", {"material_id": "M01", "platform": "douyin", "decision_basis": "核对版权和安全规则"}),
            (
                "check_slot",
                {
                    "account_id": "official_cn",
                    "start": "2026-11-06T18:00:00+08:00",
                    "duration_minutes": 30,
                    "decision_basis": "核对用户指定时段",
                },
            ),
            (
                "find_slots",
                {
                    "account_id": "official_cn",
                    "requested_start": "2026-11-06T18:00:00+08:00",
                    "duration_minutes": 30,
                    "decision_basis": "冲突后查找候选",
                },
            ),
            (
                "finish",
                {
                    "task_status": "NEEDS_CONFIRMATION",
                    "reason": "18:00 已占用，19:00 可供确认。",
                    "suggested_start": "2026-11-06T19:00:00+08:00",
                    "confirmation_status": "PENDING",
                },
            ),
        ]
    )
    result = runner(client, tmp_path).run(task("M01", "2026-11-06T18:00:00+08:00", True))
    assert result["task_status"] == "NEEDS_CONFIRMATION"
    assert result["suggested_start"] == "2026-11-06T19:00:00+08:00"
    assert result["save_status"] == "NOT_ATTEMPTED"
    assert [step["tool"] for step in result["trace"]] == [
        "get_material",
        "check_rules",
        "check_slot",
        "find_slots",
        "finish",
    ]
    assert result["trace"][0]["next_action"] == "check_rules"
    assert result["trace"][-1]["next_action"] == "END"


def test_react_path_blocks_high_risk_without_schedule_call(tmp_path: Path) -> None:
    client = ScriptedClient(
        [
            ("get_material", {"material_id": "M03"}),
            ("check_rules", {"material_id": "M03", "platform": "douyin"}),
            (
                "finish",
                {"task_status": "BLOCKED", "reason": "视频审核发现高风险内容。"},
            ),
        ]
    )
    result = runner(client, tmp_path).run(task("M03", "2026-11-06T19:00:00+08:00"))
    assert result["task_status"] == "BLOCKED"
    assert result["review_status"] == "BLOCKED"
    assert [step["tool"] for step in result["trace"]] == ["get_material", "check_rules", "finish"]


def test_react_path_saves_only_after_passed_review(tmp_path: Path) -> None:
    client = ScriptedClient(
        [
            ("get_material", {"material_id": "M01"}),
            ("check_rules", {"material_id": "M01", "platform": "douyin"}),
            (
                "save_draft",
                {
                    "material_id": "M01",
                    "start": "2026-11-06T19:00:00+08:00",
                    "confirmation_status": "NOT_REQUIRED",
                },
            ),
            ("finish", {"task_status": "COMPLETED", "reason": "审核通过并保存草稿。"}),
        ]
    )
    result = runner(client, tmp_path).run(task("M01", "2026-11-06T19:00:00+08:00"))
    assert result["task_status"] == "COMPLETED"
    assert result["save_status"] == "SAVED"
    assert result["trace"][2]["return_summary"]["duplicate"] is False


def test_react_path_cannot_save_an_unconfirmed_alternative(tmp_path: Path) -> None:
    client = ScriptedClient(
        [
            ("get_material", {"material_id": "M01"}),
            ("check_rules", {"material_id": "M01", "platform": "douyin"}),
            (
                "save_draft",
                {
                    "material_id": "M01",
                    "start": "2026-11-06T19:00:00+08:00",
                    "confirmation_status": "CONFIRMED",
                },
            ),
            ("finish", {"task_status": "BLOCKED", "reason": "未获得用户对替代时段的确认。"}),
        ]
    )
    result = runner(client, tmp_path).run(task("M01", "2026-11-06T18:00:00+08:00", True))
    assert result["trace"][2]["return_summary"]["reason_code"] == "HARD_TIME_CHANGE_REQUIRES_CONFIRMATION"
    assert result["save_status"] == "NOT_ATTEMPTED"


def test_save_cannot_escape_task_materials(tmp_path: Path) -> None:
    client = ScriptedClient(
        [
            ("check_rules", {"material_id": "M03", "platform": "douyin"}),
            (
                "save_draft",
                {
                    "material_id": "M03",
                    "start": "2026-11-06T19:00:00+08:00",
                    "confirmation_status": "NOT_REQUIRED",
                },
            ),
            ("finish", {"task_status": "BLOCKED", "reason": "素材不在当前任务。"}),
        ]
    )
    result = runner(client, tmp_path).run(task("M01", "2026-11-06T19:00:00+08:00"))
    assert result["trace"][1]["return_summary"]["reason_code"] == "MATERIAL_NOT_IN_TASK"


def test_offline_client_follows_tool_result_for_conflict(tmp_path: Path) -> None:
    catalog = DataCatalog(ROOT / "data")
    agent = AgentRunner(OfflineScenarioClient(), build_dependencies(catalog, tmp_path / "offline.sqlite"))
    result = agent.run(task("M01", "2026-11-06T18:00:00+08:00", True))
    assert result["task_status"] == "NEEDS_CONFIRMATION"
    assert result["trace"][2]["return_summary"]["available"] is False
    assert result["trace"][3]["tool"] == "find_slots"


def test_tool_call_budget_returns_incomplete(tmp_path: Path) -> None:
    client = ScriptedClient([("get_material", {"material_id": "M01"})] * 3)
    result = AgentRunner(client, build_dependencies(DataCatalog(ROOT / "data"), tmp_path / "limit.sqlite"), max_tool_calls=2).run(
        task("M01", "2026-11-06T19:00:00+08:00")
    )
    assert result["task_status"] == "INCOMPLETE"
    assert result["reason_code"] == "MAX_TOOL_CALLS"
    assert result["tool_call_count"] == 2


def test_multiple_tool_calls_are_fully_acknowledged_before_retry(tmp_path: Path) -> None:
    client = MultiCallThenScriptedClient()
    result = AgentRunner(
        client,
        build_dependencies(DataCatalog(ROOT / "data"), tmp_path / "multiple.sqlite"),
    ).run(task("M01", "2026-11-06T19:00:00+08:00"))
    assert result["task_status"] == "BLOCKED"
    assert result["trace"][0]["return_summary"]["reason_code"] == "ONE_TOOL_PER_TURN"
    assert result["trace"][1]["return_summary"]["reason_code"] == "ONE_TOOL_PER_TURN"
    second_turn_tool_ids = {
        message["tool_call_id"]
        for message in client.seen_messages[1]
        if message.get("role") == "tool"
    }
    assert second_turn_tool_ids == {"call-a", "call-b"}

