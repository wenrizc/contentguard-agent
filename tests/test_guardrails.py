from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.catalog import DataCatalog
from src.guardrails import Guardrails
from src.schemas import ReviewResult, TaskInput
from src.storage import DraftStore
from src.tools.review import ReviewTool
from src.moderation.mock import MockVideoModerator
from src.schemas import DraftInput


ROOT = Path(__file__).parents[1]
START = datetime.fromisoformat("2026-11-06T18:00:00+08:00")
ALTERNATIVE = datetime.fromisoformat("2026-11-06T19:00:00+08:00")


def task(hard_time: bool = True) -> TaskInput:
    return TaskInput(
        source_request_id="REQ-GUARD-001",
        material_ids=["M01"],
        account_id="official_cn",
        platform="douyin",
        requested_start=START,
        duration_minutes=30,
        hard_time=hard_time,
        conflict_policy="ask_before_change",
    )


def passed_review() -> ReviewResult:
    return ReviewResult(
        material_id="M01",
        review_status="PASSED",
        next_action="CONTINUE",
    )


def test_guardrails_reject_review_and_unconfirmed_time_change() -> None:
    guardrails = Guardrails()
    catalog = DataCatalog(ROOT / "data")
    review = ReviewTool(catalog, MockVideoModerator(catalog))

    pending = ReviewResult(
        material_id="M02",
        review_status="PENDING",
        next_action="REQUEST_MISSING_INFO",
    )
    rejected_review = guardrails.validate_save(task(False), "M02", pending, START, "NOT_REQUIRED")
    assert rejected_review["allowed"] is False
    assert rejected_review["reason_code"] == "REVIEW_NOT_PASSED"

    rejected_time = guardrails.validate_save(
        task(True), "M01", passed_review(), ALTERNATIVE, "PENDING"
    )
    assert rejected_time["allowed"] is False
    assert rejected_time["reason_code"] == "HARD_TIME_CHANGE_REQUIRES_CONFIRMATION"
    assert review.check_rules("M01", "douyin")["review_status"] == "PASSED"


def test_guardrails_allow_explicitly_confirmed_alternative() -> None:
    result = Guardrails().validate_save(
        task(True), "M01", passed_review(), ALTERNATIVE, "CONFIRMED"
    )
    assert result == {"allowed": True, "reason_code": "ALLOWED", "reason": "审核通过且保存权限满足。"}


def test_guardrails_reject_naive_timestamp() -> None:
    result = Guardrails().validate_save(
        task(True), "M01", passed_review(), datetime(2026, 11, 6, 19), "CONFIRMED"
    )
    assert result["allowed"] is False
    assert result["reason_code"] == "TIMEZONE_REQUIRED"


def test_store_rechecks_conflicts_inside_transaction(tmp_path: Path) -> None:
    catalog = DataCatalog(ROOT / "data")
    store = DraftStore(tmp_path / "drafts.sqlite", catalog.schedule_slots)
    draft = DraftInput(
        source_request_id="REQ-CONCURRENT-001",
        material_id="M01",
        account_id="official_cn",
        platform="douyin",
        start=ALTERNATIVE,
        duration_minutes=30,
        review_status="PASSED",
        confirmation_status="CONFIRMED",
    )
    first = store.save_draft(draft)
    second = store.save_draft(draft.model_copy(update={"source_request_id": "REQ-CONCURRENT-002"}))
    assert first["save_status"] == "SAVED"
    assert second["save_status"] == "FAILED"
    assert second["reason_code"] == "SLOT_CONFLICT"


def test_store_initialization_failure_is_reported_on_save(tmp_path: Path) -> None:
    database_path = tmp_path / "database-directory"
    database_path.mkdir()
    store = DraftStore(database_path)
    result = store.save_draft(
        DraftInput(
            source_request_id="REQ-INIT-FAIL-001",
            material_id="M01",
            account_id="official_cn",
            platform="douyin",
            start=ALTERNATIVE,
            duration_minutes=30,
            review_status="PASSED",
            confirmation_status="NOT_REQUIRED",
        )
    )
    assert result["save_status"] == "FAILED"

