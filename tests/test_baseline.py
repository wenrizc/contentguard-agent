from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schemas import TaskInput


ROOT = Path(__file__).parents[1]


def load_json(path: str) -> dict:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_baseline_data_has_six_materials_and_matching_mock_results() -> None:
    materials = load_json("data/materials.json")["materials"]
    moderation = load_json("data/moderation_mock.json")["results"]

    material_ids = {item["material_id"] for item in materials}
    moderation_ids = {item["material_id"] for item in moderation}
    assert material_ids == {"M01", "M02", "M03", "M04", "M05", "M06"}
    assert moderation_ids == material_ids


def test_baseline_data_contains_required_scenarios() -> None:
    moderation = load_json("data/moderation_mock.json")["results"]
    statuses = {item["material_id"]: item["status"] for item in moderation}
    assert statuses == {
        "M01": "PASSED",
        "M02": "PASSED",
        "M03": "BLOCKED",
        "M04": "PASSED",
        "M05": "ERROR",
        "M06": "UNKNOWN",
    }
    assert load_json("data/authorizations.json")["copyright_authorizations"]
    assert load_json("data/review_rules.json")["rules"]
    assert load_json("data/schedules.json")["slots"]


def test_cli_help_starts() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "审核短视频素材" in result.stdout
    assert "plan" in result.stdout
    assert "confirm" in result.stdout


def test_v1_task_accepts_one_material_only() -> None:
    with pytest.raises(ValidationError):
        TaskInput.model_validate(
            {
                "source_request_id": "REQ-BATCH-001",
                "material_ids": ["M01", "M02"],
                "account_id": "official_cn",
                "platform": "douyin",
                "requested_start": "2026-11-06T19:00:00+08:00",
                "duration_minutes": 30,
                "hard_time": False,
                "conflict_policy": "ask_before_change",
            }
        )

