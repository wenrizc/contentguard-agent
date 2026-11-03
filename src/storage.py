"""SQLite persistence for schedule drafts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schemas import DraftInput


class DraftStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

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

    def save_draft(self, draft: DraftInput) -> dict:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
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
                        draft.start.isoformat(),
                        draft.duration_minutes,
                        draft.review_status,
                        draft.confirmation_status,
                        _json_dumps(draft.evidence),
                    ),
                )
                duplicate = cursor.rowcount == 0
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
                        draft.start.isoformat(),
                    ),
                ).fetchone()
            return {
                "save_status": "SAVED",
                "duplicate": duplicate,
                "draft": dict(row) if row else None,
            }
        except (OSError, sqlite3.Error) as exc:
            return {
                "save_status": "FAILED",
                "duplicate": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }


def _json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)

