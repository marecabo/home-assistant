"""Config flow to configure Vorwerk integration."""
from __future__ import annotations

import logging

from pybotvac import Account
from pybotvac.exceptions import NeatoException
from requests.models import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_TOKEN

from . import api

# pylint: disable=unused-import
from .const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_PERSISTENT_MAPS,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)

DOCS_URL = "https://www.home-assistant.io/integrations/vorwerk"

_LOGGER = logging.getLogger(__name__)


class VorwerkConfigFlow(config_entries.ConfigFlow, domain=VORWERK_DOMAIN):
    """Vorwerk integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._email: str | None = None
        self._session = api.VorwerkSession()

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""

        if user_input is not None:
            self._email = user_input.get(CONF_EMAIL)
            if self._email:
                await self.async_set_unique_id(self._email)
                self._abort_if_unique_id_configured()
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                }
            ),
            description_placeholders={"docs_url": DOCS_URL},
        )

    async def async_step_code(self, user_input=None):
        """Step when user enters OTP Code from email."""
        assert self._email is not None  # typing
        errors = {}
        code = user_input.get(CONF_CODE) if user_input else None
        if code:
            try:
                # get config of robots
                robots = await self.hass.async_add_executor_job(
                    self._get_robots, self._email, code
                )
                # get persistent maps of robots
                persistent_maps = await self.hass.async_add_executor_job(
                    self._get_persistent_maps
                )
                # add persistent maps info to robot config
                for robot_serial, maps in persistent_maps.items():
                    for i, robot_config in enumerate(robots):
                        if robot_config[VORWERK_ROBOT_SERIAL] == robot_serial:
                            robots[i].update(
                                {
                                    VORWERK_ROBOT_PERSISTENT_MAPS: maps,
                                }
                            )
                _LOGGER.debug(robots)
                return self.async_create_entry(
                    title=self._email,
                    data={
                        CONF_EMAIL: self._email,
                        CONF_TOKEN: self._session.token,
                        VORWERK_ROBOTS: robots,
                    },
                )
            except (HTTPError, NeatoException):
                errors["base"] = "invalid_auth"

        await self.hass.async_add_executor_job(
            self._session.send_email_otp, self._email
        )

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODE): str,
                }
            ),
            description_placeholders={"docs_url": DOCS_URL},
            errors=errors,
        )

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        unique_id = "from configuration"
        data = {VORWERK_ROBOTS: user_input}

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(data)

        _LOGGER.info("Creating new Vorwerk robot config entry")
        return self.async_create_entry(
            title="from configuration",
            data=data,
        )

    def _get_robots(self, email: str, code: str):
        """Fetch the robot list from vorwerk."""
        self._session.fetch_token_passwordless(email, code)
        return [
            {
                VORWERK_ROBOT_NAME: robot["name"],
                VORWERK_ROBOT_SERIAL: robot["serial"],
                VORWERK_ROBOT_SECRET: robot["secret_key"],
                VORWERK_ROBOT_TRAITS: robot["traits"],
                VORWERK_ROBOT_ENDPOINT: robot["nucleo_url"],
            }
            for robot in self._session.get("users/me/robots").json()
        ]

    def _get_persistent_maps(self):
        """Fetch id, name and image of persistent maps."""
        account = Account(self._session)
        persistent_maps = account.persistent_maps.copy()
        _LOGGER.debug("Persistent Maps: %s", persistent_maps)

        for robot_serial, maps in persistent_maps.items():
            _LOGGER.debug("Found persistent maps: %s", [m["name"] for m in maps])
            for i, map in enumerate(maps):
                # download image of map
                persistent_maps[robot_serial][i].update(
                    {"image": account.get_map_image(map["url"]).data}
                )
                # remove keys which are unnecessary in config
                for key in ["url", "raw_floor_map_url", "url_valid_for_seconds"]:
                    del persistent_maps[robot_serial][i][key]
        return persistent_maps
