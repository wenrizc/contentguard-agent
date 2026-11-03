"""Side-effect boundaries for saving a schedule draft."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from .schemas import ReviewResult, TaskInput


class Guardrails:
    """Validate authorization facts before a write is dispatched.

    This class does not select another time or another tool. It only returns
    a typed permit or the violated rule for the caller to show the model.
    """

    def validate_save(
        self,
        task: TaskInput,
        material_id: str,
        review: ReviewResult,
        proposed_start: datetime,
        confirmation_status: Literal["PENDING", "CONFIRMED", "NOT_REQUIRED"],
    ) -> dict:
        if task.requested_start.tzinfo is None or proposed_start.tzinfo is None:
            return self._reject(
                "TIMEZONE_REQUIRED",
                "任务时段和待保存时段必须包含时区。",
            )
        if review.material_id != material_id:
            return self._reject(
                "MATERIAL_MISMATCH",
                "审核结果的 material_id 必须与待保存素材一致。",
            )
        if review.review_status != "PASSED":
            return self._reject(
                "REVIEW_NOT_PASSED",
                "只有 review_status=PASSED 的素材可以保存排期草稿。",
                review_status=review.review_status,
            )

        changed_time = proposed_start != task.requested_start
        if changed_time and confirmation_status != "CONFIRMED":
            code = "HARD_TIME_CHANGE_REQUIRES_CONFIRMATION" if task.hard_time else "CONFIRMATION_REQUIRED"
            return self._reject(
                code,
                "候选时段与原始请求不同，必须先取得用户对该时段的显式确认。",
                requested_start=task.requested_start.isoformat(),
                proposed_start=proposed_start.isoformat(),
            )

        if not changed_time and confirmation_status == "PENDING":
            return self._reject(
                "CONFIRMATION_STATUS_INVALID",
                "原始请求时段保存时不能标记为待确认。",
            )

        return {
            "allowed": True,
            "reason_code": "ALLOWED",
            "reason": "审核通过且保存权限满足。",
        }

    @staticmethod
    def _reject(code: str, reason: str, **details: str) -> dict:
        return {"allowed": False, "reason_code": code, "reason": reason, "details": details}

