"""Synthetic video moderation provider used by V1."""

from __future__ import annotations

from ..catalog import DataCatalog
from ..schemas import ModerationResult


class MockVideoModerator:
    provider = "mock"

    def __init__(self, catalog: DataCatalog) -> None:
        self.catalog = catalog

    def moderate(self, material_id: str) -> ModerationResult:
        result = self.catalog.moderation_results.get(material_id)
        if result is None:
            return ModerationResult(
                material_id=material_id,
                status="UNKNOWN",
                findings=None,
                evidence_source="simulated_missing_result",
            )
        return result

