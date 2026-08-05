"""Config and options flows for Kimai."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, selector

from .api import (
    KimaiApiClient,
    KimaiApiError,
    KimaiAuthenticationError,
    KimaiConnectionError,
)
from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_DEFAULT_ACTIVITY_ID,
    CONF_DEFAULT_PROJECT_ID,
    DOMAIN,
)
from .coordinator import KimaiConfigEntry
from .models import KimaiActivity, KimaiCustomer, KimaiProject

_LOGGER = logging.getLogger(__name__)


def _credentials_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the credentials form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_URL,
                default=defaults.get(CONF_BASE_URL, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Required(CONF_API_TOKEN): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


class KimaiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Kimai config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure a Kimai account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            client = KimaiApiClient(
                aiohttp_client.async_get_clientsession(self.hass),
                base_url,
                user_input[CONF_API_TOKEN],
            )
            try:
                profile = await client.async_get_profile()
            except KimaiAuthenticationError:
                errors["base"] = "invalid_auth"
            except KimaiConnectionError:
                errors["base"] = "cannot_connect"
            except KimaiApiError, ValueError:
                _LOGGER.exception("Unexpected response while validating Kimai")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{base_url}#{profile.id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Kimai — {profile.display_name}",
                    data={
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                        CONF_BASE_URL: base_url,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm(
            {CONF_BASE_URL: entry_data[CONF_BASE_URL]}
        )

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Replace an expired or revoked API token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None and CONF_API_TOKEN in user_input:
            client = KimaiApiClient(
                aiohttp_client.async_get_clientsession(self.hass),
                entry.data[CONF_BASE_URL],
                user_input[CONF_API_TOKEN],
            )
            try:
                await client.async_get_profile()
            except KimaiAuthenticationError:
                errors["base"] = "invalid_auth"
            except KimaiConnectionError:
                errors["base"] = "cannot_connect"
            except KimaiApiError, ValueError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: KimaiConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return KimaiOptionsFlow(config_entry)


class KimaiOptionsFlow(OptionsFlow):
    """Configure default project and activity for Kimai actions."""

    def __init__(self, config_entry: KimaiConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = config_entry
        self._projects: list[KimaiProject] = []
        self._activities: list[KimaiActivity] = []
        self._customers: list[KimaiCustomer] = []

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose defaults used when action fields are omitted."""
        errors: dict[str, str] = {}
        if not self._projects:
            client = KimaiApiClient(
                aiohttp_client.async_get_clientsession(self.hass),
                self._entry.data[CONF_BASE_URL],
                self._entry.data[CONF_API_TOKEN],
            )
            try:
                self._customers = await client.async_get_customers()
                self._projects = await client.async_get_projects()
                self._activities = await client.async_get_activities()
            except KimaiAuthenticationError:
                errors["base"] = "invalid_auth"
            except KimaiConnectionError:
                errors["base"] = "cannot_connect"
            except KimaiApiError, ValueError:
                errors["base"] = "unknown"

        if user_input is not None and not errors:
            project_id = int(user_input[CONF_DEFAULT_PROJECT_ID])
            activity_id = int(user_input[CONF_DEFAULT_ACTIVITY_ID])
            activity = next(
                (item for item in self._activities if item.id == activity_id), None
            )
            if activity is None or activity.project_id not in {None, project_id}:
                errors["base"] = "incompatible_activity"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_DEFAULT_ACTIVITY_ID: activity_id,
                        CONF_DEFAULT_PROJECT_ID: project_id,
                    },
                )

        if errors and not self._projects:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        if not self._projects or not self._activities:
            errors["base"] = "no_projects" if not self._projects else "no_activities"
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        customer_names = {item.id: item.name for item in self._customers}
        project_names = {item.id: item.name for item in self._projects}
        project_options = [
            selector.SelectOptionDict(
                value=str(project.id),
                label=" / ".join(
                    part
                    for part in (customer_names.get(project.customer_id), project.name)
                    if part
                ),
            )
            for project in self._projects
        ]
        activity_options = [
            selector.SelectOptionDict(
                value=str(activity.id),
                label=" — ".join(
                    part
                    for part in (
                        activity.name,
                        project_names.get(activity.project_id)
                        if activity.project_id is not None
                        else "Global",
                    )
                    if part
                ),
            )
            for activity in self._activities
        ]
        defaults = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEFAULT_PROJECT_ID,
                        default=str(
                            defaults.get(
                                CONF_DEFAULT_PROJECT_ID,
                                self._projects[0].id,
                            )
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=project_options)
                    ),
                    vol.Required(
                        CONF_DEFAULT_ACTIVITY_ID,
                        default=str(
                            defaults.get(
                                CONF_DEFAULT_ACTIVITY_ID,
                                self._activities[0].id,
                            )
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=activity_options)
                    ),
                }
            ),
            errors=errors,
        )
