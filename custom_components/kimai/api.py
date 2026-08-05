"""Asynchronous client for the Kimai JSON API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp

from .models import (
    KimaiActivity,
    KimaiCustomer,
    KimaiProfile,
    KimaiProject,
    KimaiTimesheet,
)

_LOGGER = logging.getLogger(__name__)

PAGE_SIZE = 50


class KimaiApiError(Exception):
    """Base exception raised for a Kimai API failure."""


class KimaiAuthenticationError(KimaiApiError):
    """Raised when Kimai rejects the API token."""


class KimaiConnectionError(KimaiApiError):
    """Raised when the Kimai instance cannot be reached."""


class KimaiResponseError(KimaiApiError):
    """Raised when Kimai returns an invalid or unsuccessful response."""

    def __init__(self, status: int, message: str) -> None:
        """Initialize the error."""
        super().__init__(f"Kimai returned HTTP {status}: {message}")
        self.status = status


def format_kimai_datetime(value: datetime) -> str:
    """Format local wall time as required by the Kimai API."""
    return value.strftime("%Y-%m-%dT%H:%M:%S")


class KimaiApiClient:
    """Thin async wrapper around the supported Kimai API endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_token: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

    async def _request(
        self,
        method: str,
        api_path: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Perform one authenticated request."""
        url = f"{self.base_url}/api/{api_path.lstrip('/')}"
        try:
            async with asyncio.timeout(30):
                response = await self._session.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params,
                    json=json_data,
                )
                async with response:
                    if response.status in {401, 403}:
                        raise KimaiAuthenticationError("Invalid Kimai API token")
                    if response.status >= 400:
                        body = (await response.text())[:500]
                        raise KimaiResponseError(response.status, body)
                    if response.status == 204:
                        return None
                    try:
                        return await response.json()
                    except (aiohttp.ContentTypeError, ValueError) as err:
                        msg = "Kimai returned a non-JSON response"
                        raise KimaiResponseError(response.status, msg) from err
        except TimeoutError as err:
            raise KimaiConnectionError("Timed out while connecting to Kimai") from err
        except aiohttp.ClientError as err:
            raise KimaiConnectionError(str(err)) from err

    async def async_get_profile(self) -> KimaiProfile:
        """Return the authenticated user."""
        payload = await self._request("GET", "users/me")
        return KimaiProfile.from_api(payload)

    async def async_get_customers(self) -> list[KimaiCustomer]:
        """Return visible customers."""
        payload = await self._request("GET", "customers", params={"visible": 1})
        return [KimaiCustomer.from_api(item) for item in payload]

    async def async_get_projects(self) -> list[KimaiProject]:
        """Return visible projects."""
        payload = await self._request("GET", "projects", params={"visible": 1})
        return [KimaiProject.from_api(item) for item in payload]

    async def async_get_activities(self) -> list[KimaiActivity]:
        """Return visible activities."""
        payload = await self._request("GET", "activities", params={"visible": 1})
        return [KimaiActivity.from_api(item) for item in payload]

    async def async_get_timesheets(
        self,
        begin: datetime,
        end: datetime,
    ) -> list[KimaiTimesheet]:
        """Return all timesheets overlapping a local datetime range."""
        results: list[KimaiTimesheet] = []
        page = 1
        while True:
            payload = await self._request(
                "GET",
                "timesheets",
                params={
                    "begin": format_kimai_datetime(begin),
                    "end": format_kimai_datetime(end),
                    "order": "ASC",
                    "orderBy": "begin",
                    "page": page,
                    "size": PAGE_SIZE,
                },
            )
            batch = [KimaiTimesheet.from_api(item) for item in payload]
            results.extend(batch)
            if len(batch) < PAGE_SIZE:
                return results
            page += 1

    async def async_create_timesheet(
        self,
        *,
        project_id: int,
        activity_id: int,
        begin: datetime,
        end: datetime,
        description: str,
        billable: bool,
    ) -> KimaiTimesheet:
        """Create one completed timesheet entry."""
        payload = await self._request(
            "POST",
            "timesheets",
            json_data={
                "activity": activity_id,
                "begin": format_kimai_datetime(begin),
                "billable": billable,
                "description": description,
                "end": format_kimai_datetime(end),
                "project": project_id,
            },
        )
        return KimaiTimesheet.from_api(payload)

    async def async_update_timesheet(
        self,
        timesheet_id: int,
        *,
        project_id: int,
        activity_id: int,
        begin: datetime,
        end: datetime,
        description: str,
        billable: bool,
    ) -> KimaiTimesheet:
        """Update one completed timesheet entry."""
        payload = await self._request(
            "PATCH",
            f"timesheets/{timesheet_id}",
            json_data={
                "activity": activity_id,
                "begin": format_kimai_datetime(begin),
                "billable": billable,
                "description": description,
                "end": format_kimai_datetime(end),
                "project": project_id,
            },
        )
        return KimaiTimesheet.from_api(payload)
