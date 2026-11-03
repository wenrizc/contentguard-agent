"""Schedule lookup tools."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..catalog import DataCatalog
from ..schemas import ScheduleSlot


def _end(start: datetime, duration_minutes: int) -> datetime:
    return start + timedelta(minutes=duration_minutes)


def _overlaps(start: datetime, end: datetime, slot: ScheduleSlot) -> bool:
    return slot.status in {"CONFIRMED", "DRAFT"} and start < slot.end and end > slot.start


class ScheduleTool:
    def __init__(self, catalog: DataCatalog) -> None:
        self.catalog = catalog

    def check_slot(self, account_id: str, start: datetime, duration_minutes: int) -> dict:
        end = _end(start, duration_minutes)
        conflicts = [
            slot.model_dump(mode="json")
            for slot in self.catalog.schedule_slots
            if slot.account_id == account_id and _overlaps(start, end, slot)
        ]
        return {
            "account_id": account_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "available": not conflicts,
            "conflicts": conflicts,
        }

    def find_slots(
        self,
        account_id: str,
        requested_start: datetime,
        duration_minutes: int,
        limit: int = 3,
    ) -> dict:
        # Candidate times use the business hourly grid; the model may present
        # these to the user but cannot treat them as confirmed.
        first_hour = requested_start.replace(minute=0, second=0, microsecond=0)
        if first_hour < requested_start:
            first_hour += timedelta(hours=1)
        candidates = []
        for offset in range(0, 24):
            candidate = first_hour + timedelta(hours=offset)
            checked = self.check_slot(account_id, candidate, duration_minutes)
            if checked["available"]:
                candidates.append({"start": checked["start"], "end": checked["end"]})
                if len(candidates) >= limit:
                    break
        return {
            "account_id": account_id,
            "requested_start": requested_start.isoformat(),
            "duration_minutes": duration_minutes,
            "candidates": candidates,
        }

