"""MyJDownloader switches."""

import datetime
import logging

from myjdapi.myjdapi import MYJDException

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_UNKNOWN

from . import MyJDownloaderHub
from .const import DATA_MYJDOWNLOADER_CLIENT, DOMAIN, SCAN_INTERVAL_SECONDS
from .entities import MyJDownloaderDeviceEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=SCAN_INTERVAL_SECONDS)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor using config entry."""
    dev = []
    hub = hass.data[DOMAIN][entry.entry_id][DATA_MYJDOWNLOADER_CLIENT]
    for device_id in hub.devices.keys():
        dev += [
            MyJDownloaderPauseSwitch(hub, device_id),
            MyJDownloaderLimitSwitch(hub, device_id),
        ]
    async_add_entities(dev, True)


class MyJDownloaderSwitch(MyJDownloaderDeviceEntity, SwitchEntity):
    """Defines a MyJDownloader switch."""

    def __init__(
        self,
        hub: MyJDownloaderHub,
        device_id: str,
        name: str,
        icon: str,
        key: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize MyJDownloader switch."""
        self._state = False
        self._key = key
        super().__init__(hub, device_id, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join([DOMAIN, self._name, "switch", self._key])

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._state

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        try:
            await self._myjdownloader_turn_off()
        except MYJDException:
            _LOGGER.error("An error occurred while turning off MyJDownloader switch")
            self._available = False

    async def _myjdownloader_turn_off(self) -> None:
        """Turn off the switch."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        try:
            await self._myjdownloader_turn_on()
        except MYJDException:
            _LOGGER.error("An error occurred while turning on MyJDownloader switch")
            self._available = False

    async def _myjdownloader_turn_on(self) -> None:
        """Turn on the switch."""
        raise NotImplementedError()


class MyJDownloaderPauseSwitch(MyJDownloaderSwitch):
    """Defines a MyJDownloader pause switch."""

    def __init__(
        self,
        hub: MyJDownloaderHub,
        device_id: str,
    ) -> None:
        """Initialize MyJDownloader switch."""
        super().__init__(
            hub,
            device_id,
            "JDownloader $device_name Pause",
            "mdi:play-pause",
            "pause",
        )

    async def _myjdownloader_turn_off(self) -> None:
        """Turn off the switch."""
        # TODO additionally trigger update of status sensor immediately
        # http://dev-docs.home-assistant.io/en/master/api/helpers.html#module-homeassistant.helpers.dispatcher
        device = self.hub.get_device(self._device_id)
        await self.hub.async_query(device.downloadcontroller.pause_downloads, False)

    async def _myjdownloader_turn_on(self) -> None:
        """Turn on the switch."""
        # TODO additionally trigger update of status sensor immediately
        # http://dev-docs.home-assistant.io/en/master/api/helpers.html#module-homeassistant.helpers.dispatcher
        device = self.hub.get_device(self._device_id)
        await self.hub.async_query(device.downloadcontroller.pause_downloads, True)

    async def _myjdownloader_update(self) -> None:
        """Update MyJDownloader entity."""
        device = self.hub.get_device(self._device_id)
        status = await self.hub.async_query(device.downloadcontroller.get_current_state)
        if not status:
            current_state = STATE_UNKNOWN
        else:
            current_state = status.lower() == "pause"
        self._state = current_state


class MyJDownloaderLimitSwitch(MyJDownloaderSwitch):
    """Defines a MyJDownloader limit switch."""

    def __init__(
        self,
        hub: MyJDownloaderHub,
        device_id: str,
    ) -> None:
        """Initialize MyJDownloader switch."""
        super().__init__(
            hub,
            device_id,
            "JDownloader $device_name Limit",
            "mdi:download-lock",
            "limit",
        )

    async def _myjdownloader_turn_off(self) -> None:
        """Turn off the switch."""
        device = self.hub.get_device(self._device_id)
        await self.hub.async_query(device.toolbar.disable_downloadSpeedLimit)

    async def _myjdownloader_turn_on(self) -> None:
        """Turn on the switch."""
        device = self.hub.get_device(self._device_id)
        await self.hub.async_query(device.toolbar.enable_downloadSpeedLimit)

    async def _myjdownloader_update(self) -> None:
        """Update MyJDownloader entity."""
        device = self.hub.get_device(self._device_id)
        try:
            self._state = await self.hub.async_query(
                device.toolbar.status_downloadSpeedLimit
            )
        except TypeError as ex:
            # gets raised when device is not online anymore
            self._state = STATE_UNKNOWN
            raise Exception() from ex
