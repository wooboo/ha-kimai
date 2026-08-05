"""Typed models used by the Kimai integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


def _integer_id(value: Any) -> int | None:
    """Extract an integer ID from a Kimai scalar or embedded object."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, dict):
        return _integer_id(value.get("id"))
    return None


def parse_kimai_datetime(value: str | None) -> datetime | None:
    """Parse a datetime returned by Kimai."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True, slots=True)
class KimaiCustomer:
    """A Kimai customer."""

    id: int
    name: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> KimaiCustomer:
        """Create a customer from an API response."""
        customer_id = _integer_id(payload.get("id"))
        if customer_id is None:
            msg = "Kimai customer is missing an integer id"
            raise ValueError(msg)
        return cls(id=customer_id, name=str(payload.get("name") or customer_id))


@dataclass(frozen=True, slots=True)
class KimaiProject:
    """A Kimai project."""

    id: int
    name: str
    customer_id: int | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> KimaiProject:
        """Create a project from an API response."""
        project_id = _integer_id(payload.get("id"))
        if project_id is None:
            msg = "Kimai project is missing an integer id"
            raise ValueError(msg)
        return cls(
            id=project_id,
            name=str(payload.get("name") or project_id),
            customer_id=_integer_id(payload.get("customer")),
        )


@dataclass(frozen=True, slots=True)
class KimaiActivity:
    """A Kimai activity."""

    id: int
    name: str
    project_id: int | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> KimaiActivity:
        """Create an activity from an API response."""
        activity_id = _integer_id(payload.get("id"))
        if activity_id is None:
            msg = "Kimai activity is missing an integer id"
            raise ValueError(msg)
        return cls(
            id=activity_id,
            name=str(payload.get("name") or activity_id),
            project_id=_integer_id(payload.get("project")),
        )


@dataclass(frozen=True, slots=True)
class KimaiTimesheet:
    """A Kimai timesheet entry."""

    id: int
    begin: datetime
    end: datetime | None
    duration_seconds: int
    project_id: int | None
    activity_id: int | None
    description: str
    billable: bool

    @property
    def hours(self) -> float:
        """Return the recorded duration in decimal hours."""
        return self.duration_seconds / 3600

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> KimaiTimesheet:
        """Create a timesheet from an API response."""
        timesheet_id = _integer_id(payload.get("id"))
        begin = parse_kimai_datetime(payload.get("begin"))
        if timesheet_id is None or begin is None:
            msg = "Kimai timesheet is missing id or begin"
            raise ValueError(msg)

        end = parse_kimai_datetime(payload.get("end"))
        raw_duration = payload.get("duration")
        if isinstance(raw_duration, int | float):
            duration_seconds = max(0, int(raw_duration))
        elif end is not None:
            duration_seconds = max(0, int((end - begin).total_seconds()))
        else:
            duration_seconds = 0

        return cls(
            id=timesheet_id,
            begin=begin,
            end=end,
            duration_seconds=duration_seconds,
            project_id=_integer_id(payload.get("project")),
            activity_id=_integer_id(payload.get("activity")),
            description=str(payload.get("description") or ""),
            billable=bool(payload.get("billable", True)),
        )


@dataclass(frozen=True, slots=True)
class KimaiProfile:
    """The authenticated Kimai user."""

    id: int
    display_name: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> KimaiProfile:
        """Create a user profile from an API response."""
        user_id = _integer_id(payload.get("id"))
        if user_id is None:
            msg = "Kimai profile is missing an integer id"
            raise ValueError(msg)
        display_name = (
            payload.get("displayName")
            or payload.get("alias")
            or payload.get("username")
            or user_id
        )
        return cls(id=user_id, display_name=str(display_name))


@dataclass(frozen=True, slots=True)
class KimaiSnapshot:
    """Data shared by Kimai entities after a coordinated refresh."""

    customers: tuple[KimaiCustomer, ...]
    projects: tuple[KimaiProject, ...]
    activities: tuple[KimaiActivity, ...]
    timesheets: tuple[KimaiTimesheet, ...]

    def project_name(self, project_id: int | None) -> str:
        """Return a human-friendly project label."""
        project = next((item for item in self.projects if item.id == project_id), None)
        if project is None:
            return "Unknown project"
        customer = next(
            (item for item in self.customers if item.id == project.customer_id), None
        )
        if customer is None:
            return project.name
        return f"{customer.name} / {project.name}"

    def activity_name(self, activity_id: int | None) -> str:
        """Return a human-friendly activity label."""
        activity = next(
            (item for item in self.activities if item.id == activity_id), None
        )
        return activity.name if activity is not None else "Unknown activity"

    def hours_for_date(self, selected_date: date) -> float:
        """Return total recorded hours for a local Kimai date."""
        return sum(
            item.hours for item in self.timesheets if item.begin.date() == selected_date
        )
