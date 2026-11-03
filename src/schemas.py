"""Typed contracts shared by deterministic tools and the ReAct runner."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return value


class Material(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    title: str
    media_uri: str
    duration_seconds: int = Field(gt=0)
    subtitle_text: str
    platforms: list[str]
    brand_tags: list[str]
    copyright_reference: str | None = None


class Authorization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    reference: str
    scope: list[str]
    valid_until: datetime
    status: Literal["VALID", "EXPIRED", "REVOKED"]

    _valid_until_timezone = field_validator("valid_until")(_require_timezone)


class ModerationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    severity: Literal["low", "medium", "high"]
    timestamp_seconds: float | None = None
    evidence_source: str


class ModerationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    material_id: str
    status: Literal["PASSED", "BLOCKED", "ERROR", "UNKNOWN"]
    findings: list[ModerationFinding] | None = None
    evidence_source: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    name: str
    category: str
    severity: Literal["low", "medium", "high"]
    action: Literal["REQUEST_MISSING_INFO", "BLOCK"]
    match_terms: list[str] = []


class ScheduleSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    material_id: str
    start: datetime
    end: datetime
    status: Literal["CONFIRMED", "DRAFT"]

    _start_timezone = field_validator("start")(_require_timezone)
    _end_timezone = field_validator("end")(_require_timezone)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_request_id: str
    material_ids: list[str] = Field(min_length=1)
    account_id: str
    platform: str
    requested_start: datetime
    duration_minutes: int = Field(gt=0)
    hard_time: bool
    conflict_policy: Literal["ask_before_change", "reject"]

    _requested_start_timezone = field_validator("requested_start")(_require_timezone)


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_request_id: str
    material_id: str
    account_id: str
    platform: str
    start: datetime
    duration_minutes: int = Field(gt=0)
    review_status: str
    confirmation_status: Literal["PENDING", "CONFIRMED", "NOT_REQUIRED"]
    evidence: dict[str, Any] = Field(default_factory=dict)

    _start_timezone = field_validator("start")(_require_timezone)


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    category: str
    severity: Literal["low", "medium", "high"]
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    review_status: Literal["PASSED", "PENDING", "BLOCKED", "UNKNOWN", "ERROR"]
    findings: list[ReviewFinding] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    next_action: Literal["CONTINUE", "REQUEST_MISSING_INFO", "BLOCK", "RETRY_REVIEW"]

