"""Coordinator for Vallox ventilation units."""

import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from vallox_websocket_api import MetricData, Profile, Vallox, ValloxApiException

from .const import STATE_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ValloxConfigEntry = ConfigEntry[ValloxDataUpdateCoordinator]


class ValloxDataUpdateCoordinator(DataUpdateCoordinator[MetricData]):
    """The DataUpdateCoordinator for Vallox."""

    config_entry: ValloxConfigEntry

    # Profile snapshotted by start_nocturnal_cooling so stop can restore it.
    # Stored on the coordinator (the config entry's runtime_data), never on a
    # user-facing helper, so it survives across the cooling window but not a
    # restart.
    nocturnal_cooling_prev_profile: Profile | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ValloxConfigEntry,
        client: Vallox,
    ) -> None:
        """Initialize Vallox data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.data[CONF_NAME]} DataUpdateCoordinator",
            update_interval=STATE_SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> MetricData:
        """Fetch state update."""
        _LOGGER.debug("Updating Vallox state cache")

        try:
            return await self.client.fetch_metric_data()
        except ValloxApiException as err:
            raise UpdateFailed("Error during state cache update") from err
