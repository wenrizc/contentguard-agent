from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def test_cli_offline_writes_trace_and_marks_boundary(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "plan",
            "--offline",
            "--input",
            "examples/inputs/blocked.json",
            "--db",
            str(tmp_path / "drafts.sqlite"),
            "--trace",
            str(trace_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["execution_mode"] == "offline_mock"
    assert output["task_status"] == "BLOCKED"
    assert json.loads(trace_path.read_text(encoding="utf-8"))["trace"]


@pytest.mark.parametrize(
    ("input_name", "task_status", "review_status", "save_status"),
    [
        ("normal", "COMPLETED", "PASSED", "SAVED"),
        ("missing-info", "BLOCKED", "PENDING", "NOT_ATTEMPTED"),
        ("rule-risk", "BLOCKED", "BLOCKED", "NOT_ATTEMPTED"),
        ("conflict", "NEEDS_CONFIRMATION", "PASSED", "NOT_ATTEMPTED"),
        ("save-failure", "BLOCKED", "PASSED", "FAILED"),
    ],
)
def test_cli_offline_acceptance_scenarios(
    tmp_path: Path,
    input_name: str,
    task_status: str,
    review_status: str,
    save_status: str,
) -> None:
    database_path = tmp_path / f"{input_name}.sqlite"
    if input_name == "save-failure":
        database_path.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.main",
            "plan",
            "--offline",
            "--input",
            f"examples/inputs/{input_name}.json",
            "--db",
            str(database_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["task_status"] == task_status
    assert output["review_status"] == review_status
    assert output["save_status"] == save_status
    assert output["trace"]


def test_cli_offline_duplicate_submission_is_idempotent(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "src.main",
        "plan",
        "--offline",
        "--input",
        "examples/inputs/normal.json",
        "--db",
        str(tmp_path / "drafts.sqlite"),
    ]
    first = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    second = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert first.returncode == 0
    assert second.returncode == 0
    output = json.loads(second.stdout)
    save_steps = [step for step in output["trace"] if step["tool"] == "save_draft"]
    assert output["save_status"] == "SAVED"
    assert save_steps[0]["return_summary"]["duplicate"] is True

