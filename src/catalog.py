"""Load the small, synthetic data catalog used by local tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import Authorization, Material, ModerationResult, RuleDefinition, ScheduleSlot


class DataCatalog:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.materials = self._index("materials.json", "materials", Material)
        self.authorizations = self._index("authorizations.json", "copyright_authorizations", Authorization)
        self.moderation_results = self._index("moderation_mock.json", "results", ModerationResult)
        self.rules = self._load_list("review_rules.json", "rules", RuleDefinition)
        self.schedule_slots = self._load_list("schedules.json", "slots", ScheduleSlot)

    def _read(self, filename: str) -> dict[str, Any]:
        with (self.data_dir / filename).open(encoding="utf-8") as handle:
            return json.load(handle)

    def _load_list(self, filename: str, key: str, model: type[Any]) -> list[Any]:
        return [model.model_validate(item) for item in self._read(filename)[key]]

    def _index(self, filename: str, key: str, model: type[Any]) -> dict[str, Any]:
        items = self._load_list(filename, key, model)
        return {item.material_id: item for item in items}

