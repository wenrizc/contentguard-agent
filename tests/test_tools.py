from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.catalog import DataCatalog
from src.moderation.mock import MockVideoModerator
from src.schemas import DraftInput
from src.storage import DraftStore
from src.tools.material import MaterialTool
from src.tools.review import ReviewTool
from src.tools.schedule import ScheduleTool


ROOT = Path(__file__).parents[1]


def make_catalog() -> DataCatalog:
    return DataCatalog(ROOT / "data")


def test_material_tool_exposes_missing_authorization() -> None:
    result = MaterialTool(make_catalog()).get_material("M02")
    assert result["status"] == "FOUND"
    assert result["authorization"] is None


def test_review_tool_covers_pending_blocked_error_and_unknown() -> None:
    catalog = make_catalog()
    tool = ReviewTool(catalog, MockVideoModerator(catalog))

    assert tool.check_rules("M01", "douyin")["review_status"] == "PASSED"
    assert tool.check_rules("M02", "douyin")["review_status"] == "PENDING"
    assert tool.check_rules("M03", "douyin")["review_status"] == "BLOCKED"
    assert tool.check_rules("M04", "douyin")["review_status"] == "BLOCKED"
    assert tool.check_rules("M05", "douyin")["review_status"] == "ERROR"
    assert tool.check_rules("M06", "douyin")["review_status"] == "UNKNOWN"


def test_schedule_tool_reports_conflict_and_hourly_candidate() -> None:
    tool = ScheduleTool(make_catalog())
    requested = datetime.fromisoformat("2026-11-06T18:00:00+08:00")
    checked = tool.check_slot("official_cn", requested, 30)
    assert checked["available"] is False
    assert checked["conflicts"][0]["material_id"] == "existing-001"

    candidates = tool.find_slots("official_cn", requested, 30)
    assert candidates["candidates"][0]["start"] == "2026-11-06T19:00:00+08:00"


def draft() -> DraftInput:
    return DraftInput(
        source_request_id="REQ-STORE-001",
        material_id="M01",
        account_id="official_cn",
        platform="douyin",
        start=datetime.fromisoformat("2026-11-06T19:00:00+08:00"),
        duration_minutes=30,
        review_status="PASSED",
        confirmation_status="CONFIRMED",
    )


def test_draft_store_is_idempotent(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts.sqlite")
    first = store.save_draft(draft())
    second = store.save_draft(draft())
    assert first["save_status"] == "SAVED"
    assert first["duplicate"] is False
    assert second["save_status"] == "SAVED"
    assert second["duplicate"] is True


def test_draft_store_reports_write_failure(tmp_path: Path) -> None:
    database_path = tmp_path / "drafts.sqlite"
    store = DraftStore(database_path)
    database_path.unlink()
    database_path.mkdir()
    result = store.save_draft(draft())
    assert result["save_status"] == "FAILED"
    assert result["error"]["type"] in {"OperationalError", "DatabaseError"}

