# Kimai for Home Assistant

[![HACS validation](https://github.com/wooboo/ha-kimai/actions/workflows/validate.yml/badge.svg)](https://github.com/wooboo/ha-kimai/actions/workflows/validate.yml)
[![Tests](https://github.com/wooboo/ha-kimai/actions/workflows/tests.yml/badge.svg)](https://github.com/wooboo/ha-kimai/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Home Assistant custom integration for browsing and recording time in a
Kimai 2.x instance. It uses Kimai's current Bearer-token API and can work with
self-hosted or hosted installations reachable from Home Assistant.

## Features

- UI-based setup and API-token reauthentication.
- Duration sensors for today, the current week and the current month.
- A calendar entity for browsing entries and moving between days.
- `kimai.log_time` to create a completed entry.
- `kimai.get_day_hours` to read the matching total for a selected date.
- `kimai.set_day_hours` to create or update the single matching entry for a
  project, activity and date.
- Optional default project and activity configured from the integration's
  options screen.
- English and Polish translations, diagnostics with token redaction, and
  automated tests.

## Installation

Requirements: Home Assistant 2026.7 or newer and a reachable Kimai 2.x
instance with API access enabled for the user.

### HACS custom repository

1. Open HACS and select **Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/wooboo/ha-kimai` as category **Integration**.
4. Install **Kimai** and restart Home Assistant.

### Manual

Copy `custom_components/kimai` into the `custom_components` directory in your
Home Assistant configuration, then restart Home Assistant.

## Configuration

1. In Kimai, open your user profile and create an API token.
2. In Home Assistant, go to **Settings → Devices & services → Add integration**.
3. Search for **Kimai**.
4. Enter the base URL, without `/api`, and the API token. The token is not your
   Kimai password.
5. Open **Configure** on the new integration to choose the default project and
   activity used by actions.

Use HTTPS whenever Kimai is accessed over an untrusted network. The timezone
configured for the Kimai user should match Home Assistant's timezone because
Kimai's write API accepts local wall-clock datetimes.

## Entities

| Entity | Purpose |
| --- | --- |
| Today | Total completed time whose entry starts today |
| This week | Total from Monday through today |
| This month | Total in the current calendar month |
| Timesheets | Calendar of entries for any range requested by the dashboard |

The **Today** sensor also exposes a `daily_hours` attribute containing the
last seven dates. The calendar entity is the recommended native dashboard
control when you need to move farther backwards.

## Actions

### `kimai.log_time`

Creates one completed timesheet. Required fields are `date` and
`duration_hours`. `start_time` defaults to 09:00. Project and activity may be
omitted when defaults are configured.

```yaml
action: kimai.log_time
data:
  date: "2026-08-05"
  duration_hours: 7.5
  description: Home Assistant
```

### `kimai.set_day_hours`

Creates a matching entry when none exists, or updates it when exactly one
entry exists for the selected project, activity and date. It refuses to
modify the day when multiple entries match, so it cannot silently overwrite
the wrong record.

```yaml
action: kimai.set_day_hours
data:
  date: "2026-08-05"
  start_time: "09:00:00"
  duration_hours: 8.25
```

### `kimai.get_day_hours`

Returns the total duration and matching entry IDs for a selected date. Project
and activity use the integration defaults when omitted.

```yaml
action: kimai.get_day_hours
data:
  date: "2026-08-05"
response_variable: kimai_day
```

All actions accept optional `project_id` and `activity_id`. The write actions
also accept `billable` and `description`. `config_entry_id` is needed only when
multiple Kimai accounts are configured.

## Dashboard example

```yaml
type: calendar
entities:
  - calendar.kimai_timesheets
initial_view: listWeek
```

The integration deliberately does not depend on a particular attendance or
presence tracker. A dashboard can place any local duration sensor beside the
Kimai sensor and call `kimai.set_day_hours` with the corrected value.

## Development

```bash
uv sync
uv run ruff check .
uv run pytest
```

## License

[MIT](LICENSE)
