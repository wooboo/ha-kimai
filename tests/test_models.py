"""Tests for Kimai API models."""

from datetime import date

import pytest

from custom_components.kimai.models import KimaiSnapshot, KimaiTimesheet


def test_timesheet_parses_duration_and_ids() -> None:
    """A modern Kimai payload is converted to a typed model."""
    timesheet = KimaiTimesheet.from_api(
        {
            "id": 101,
            "begin": "2026-08-05T09:00:00+02:00",
            "end": "2026-08-05T16:30:00+02:00",
            "duration": 27000,
            "project": {"id": 22},
            "activity": 33,
            "description": "Focused work",
            "billable": True,
        }
    )

    assert timesheet.hours == 7.5
    assert timesheet.project_id == 22
    assert timesheet.activity_id == 33
    assert timesheet.begin.utcoffset().total_seconds() == 7200


def test_snapshot_aggregates_a_day() -> None:
    """Daily totals include all entries starting on the selected local day."""
    entries = tuple(
        KimaiTimesheet.from_api(
            {
                "id": index,
                "begin": f"2026-08-05T{hour:02}:00:00+02:00",
                "end": f"2026-08-05T{hour + 1:02}:00:00+02:00",
                "duration": 3600,
            }
        )
        for index, hour in ((1, 9), (2, 11))
    )
    snapshot = KimaiSnapshot((), (), (), entries)

    assert snapshot.hours_for_date(date(2026, 8, 5)) == 2


def test_invalid_timesheet_is_rejected() -> None:
    """Missing identity data never leaks into entity state."""
    with pytest.raises(ValueError, match="missing id or begin"):
        KimaiTimesheet.from_api({"begin": "2026-08-05T09:00:00+02:00"})
