"""SQLite persistence for schedule drafts."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .schemas import DraftInput, ScheduleSlot


class DraftStore:
    def __init__(self, database_path: Path, schedule_slots: Iterable[ScheduleSlot] = ()) -> None:
        self.database_path = database_path
        self.schedule_slots = list(schedule_slots)
        self.initialization_error: dict[str, str] | None = None
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.initialization_error = {"type": type(exc).__name__, "message": str(exc)}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_request_id TEXT NOT NULL,
                    material_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    start TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    review_status TEXT NOT NULL,
                    confirmation_status TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    UNIQUE(source_request_id, material_id, account_id, start)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS occupied_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    material_id TEXT NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    status TEXT NOT NULL,
                    UNIQUE(account_id, material_id, start, end)
                )
                """
            )
            for slot in self.schedule_slots:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO occupied_slots
                        (account_id, material_id, start, end, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        slot.account_id,
                        slot.material_id,
                        _canonical_time(slot.start),
                        _canonical_time(slot.end),
                        slot.status,
                    ),
                )

    def save_draft(self, draft: DraftInput) -> dict:
        if self.initialization_error:
            return {
                "save_status": "FAILED",
                "duplicate": False,
                "error": self.initialization_error,
            }
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT source_request_id, material_id, account_id, platform,
                           start, duration_minutes, review_status,
                           confirmation_status, evidence_json
                    FROM drafts
                    WHERE source_request_id = ? AND material_id = ?
                      AND account_id = ? AND start = ?
                    """,
                    (
                        draft.source_request_id,
                        draft.material_id,
                        draft.account_id,
                        _canonical_time(draft.start),
                    ),
                ).fetchone()
                if existing:
                    return {
                        "save_status": "SAVED",
                        "duplicate": True,
                        "draft": dict(existing),
                    }

                end = draft.start + timedelta(minutes=draft.duration_minutes)
                conflicts = connection.execute(
                    """
                    SELECT account_id, material_id, start, end, status
                    FROM occupied_slots
                    WHERE account_id = ? AND start < ? AND end > ?
                    """,
                    (draft.account_id, _canonical_time(end), _canonical_time(draft.start)),
                ).fetchall()
                if conflicts:
                    return {
                        "save_status": "FAILED",
                        "duplicate": False,
                        "reason_code": "SLOT_CONFLICT",
                        "reason": "保存前事务复核发现目标账号时段已被占用。",
                        "conflicts": [dict(item) for item in conflicts],
                    }

                connection.execute(
                    """
                    INSERT OR IGNORE INTO drafts (
                        source_request_id, material_id, account_id, platform,
                        start, duration_minutes, review_status,
                        confirmation_status, evidence_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft.source_request_id,
                        draft.material_id,
                        draft.account_id,
                        draft.platform,
                        _canonical_time(draft.start),
                        draft.duration_minutes,
                        draft.review_status,
                        draft.confirmation_status,
                        _json_dumps(draft.evidence),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO occupied_slots (account_id, material_id, start, end, status)
                    VALUES (?, ?, ?, ?, 'DRAFT')
                    """,
                    (
                        draft.account_id,
                        draft.material_id,
                        _canonical_time(draft.start),
                        _canonical_time(end),
                    ),
                )
                row = connection.execute(
                    """
                    SELECT source_request_id, material_id, account_id, platform,
                           start, duration_minutes, review_status,
                           confirmation_status, evidence_json
                    FROM drafts
                    WHERE source_request_id = ? AND material_id = ?
                      AND account_id = ? AND start = ?
                    """,
                    (
                        draft.source_request_id,
                        draft.material_id,
                        draft.account_id,
                        _canonical_time(draft.start),
                    ),
                ).fetchone()
            return {
                "save_status": "SAVED",
                "duplicate": False,
                "draft": dict(row) if row else None,
            }
        except (OSError, ValueError, sqlite3.Error) as exc:
            return {
                "save_status": "FAILED",
                "duplicate": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }


def _json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _canonical_time(value: datetime) -> str:
    """Store aware timestamps in UTC so different offsets compare correctly."""
    if value.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return value.astimezone(timezone.utc).isoformat()

