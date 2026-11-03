from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.agent import AgentRunner, build_dependencies
from src.catalog import DataCatalog
from src.llm_client import ChatResponse, ToolCall
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

