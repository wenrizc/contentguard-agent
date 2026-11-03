"""Common interface for external video moderation providers."""

from __future__ import annotations

from typing import Protocol

from ..schemas import ModerationResult


class VideoModerator(Protocol):
    provider: str

    def moderate(self, material_id: str) -> ModerationResult:
        """Return a normalized moderation result for one material."""

