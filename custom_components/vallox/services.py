"""Services for the Vallox integration."""

from __future__ import annotations

from enum import StrEnum, auto
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from vallox_websocket_api import Profile, ValloxApiException
import voluptuous as vol

from .const import (
    AWAY_AIR_TEMP_TARGET,
    COMMISSIONED_AWAY_TARGET,
    COMMISSIONED_HEATING_SEASON_SETPOINT,
    COOLING_AWAY_TARGET,
    COOLING_HEATING_SEASON_SETPOINT,
    DOMAIN,
    HEATING_SEASON_SETPOINT,
    I18N_KEY_TO_VALLOX_PROFILE,
    PROFILE_DURATION_INDEFINITE,
    SERVICE_START_NOCTURNAL_COOLING,
    SERVICE_STOP_NOCTURNAL_COOLING,
)
from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .readback import read_raw, to_c

if TYPE_CHECKING:
    from collections.abc import Mapping

_LOGGER = logging.getLogger(__name__)

ATTR_PROFILE_FAN_SPEED = "fan_speed"
ATTR_PROFILE = "profile"
ATTR_DURATION = "duration"


class ValloxService(StrEnum):
    """Vallox service names."""

    SET_PROFILE_FAN_SPEED_HOME = auto()
    SET_PROFILE_FAN_SPEED_AWAY = auto()
    SET_PROFILE_FAN_SPEED_BOOST = auto()
    SET_PROFILE = auto()
    START_NOCTURNAL_COOLING = SERVICE_START_NOCTURNAL_COOLING
    STOP_NOCTURNAL_COOLING = SERVICE_STOP_NOCTURNAL_COOLING


SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED = vol.Schema(
    {vol.Required(ATTR_PROFILE_FAN_SPEED): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=100))}
)

SERVICE_SCHEMA_SET_PROFILE = vol.Schema(
    {
        vol.Required(ATTR_PROFILE): vol.In(I18N_KEY_TO_VALLOX_PROFILE),
        vol.Optional(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=PROFILE_DURATION_INDEFINITE)
        ),
    }
)


def _get_entry(hass: HomeAssistant) -> ValloxConfigEntry:
    """Return the loaded Vallox config entry (there must be exactly one)."""
    entries: list[ValloxConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if len(entries) != 1:
        raise ValueError("Expected exactly one loaded Vallox config entry")
    return entries[0]


def _get_coordinator(
    hass: HomeAssistant,
) -> ValloxDataUpdateCoordinator:
    """Return the coordinator for the Vallox config entry."""
    return _get_entry(hass).runtime_data


async def _async_set_profile_fan_speed(call: ServiceCall, profile: Profile) -> None:
    """Set the fan speed in percent for the profile matching the called service."""
    fan_speed: int = call.data[ATTR_PROFILE_FAN_SPEED]
    _LOGGER.debug("Setting %s fan speed to: %d%%", profile.name, fan_speed)

    coordinator = _get_coordinator(call.hass)
    try:
        await coordinator.client.set_fan_speed(profile, fan_speed)
    except ValloxApiException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="failed_to_set_fan_speed_for_profile",
            translation_placeholders={
                "profile": profile.name.lower(),
                "fan_speed": str(fan_speed),
            },
        ) from err
    else:
        await coordinator.async_request_refresh()


async def _async_set_profile_fan_speed_away(call: ServiceCall) -> None:
    """Set the fan speed in percent for the Away profile."""
    await _async_set_profile_fan_speed(call, Profile.AWAY)


async def _async_set_profile_fan_speed_boost(call: ServiceCall) -> None:
    """Set the fan speed in percent for the Boost profile."""
    await _async_set_profile_fan_speed(call, Profile.BOOST)


async def _async_set_profile_fan_speed_home(call: ServiceCall) -> None:
    """Set the fan speed in percent for the Home profile."""
    await _async_set_profile_fan_speed(call, Profile.HOME)


async def _async_set_profile(call: ServiceCall) -> None:
    """Activate the given profile for the given duration."""
    profile_key: str = call.data[ATTR_PROFILE]
    duration: int | None = call.data.get(ATTR_DURATION)
    _LOGGER.debug("Activating profile %s for %s min", profile_key, duration)

    coordinator = _get_coordinator(call.hass)
    try:
        await coordinator.client.set_profile(I18N_KEY_TO_VALLOX_PROFILE[profile_key], duration)
    except ValloxApiException as err:
        placeholders = {"profile": profile_key}
        if duration is not None and duration != PROFILE_DURATION_INDEFINITE:
            placeholders["duration"] = str(duration)
            translation_key = "failed_to_set_profile_for_duration"
        else:
            translation_key = "failed_to_set_profile"
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        ) from err
    else:
        await coordinator.async_request_refresh()


# Nocturnal cooling register writes (Celsius; the client converts to
# centi-Kelvin inside set_values for known temperature metrics).
_NOCTURNAL_COOLING_WRITES: Mapping[str, float] = {
    HEATING_SEASON_SETPOINT: COOLING_HEATING_SEASON_SETPOINT,
    AWAY_AIR_TEMP_TARGET: COOLING_AWAY_TARGET,
}
_NOCTURNAL_COOLING_RESTORE: Mapping[str, float] = {
    HEATING_SEASON_SETPOINT: COMMISSIONED_HEATING_SEASON_SETPOINT,
    AWAY_AIR_TEMP_TARGET: COMMISSIONED_AWAY_TARGET,
}
# Centi-Kelvin quantisation is 0.01 C, so a 0.05 C tolerance is plenty.
_VERIFY_TOLERANCE_C = 0.05


async def _async_verify_writes(
    coordinator: ValloxDataUpdateCoordinator,
    expected: Mapping[str, float],
) -> None:
    """Confirm each expected Celsius value took hold via raw register readback."""
    raw = await read_raw(coordinator.client, list(expected))
    for key, want_c in expected.items():
        got_c = to_c(raw.get(key))
        if got_c is None or abs(got_c - want_c) > _VERIFY_TOLERANCE_C:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="nocturnal_cooling_verify_failed",
                translation_placeholders={
                    "register": key,
                    "expected": str(want_c),
                    "got": str(got_c),
                },
            )


async def async_start_nocturnal_cooling(entry: ValloxConfigEntry) -> None:
    """Lower the heating-season setpoint, set the Away target, switch to Away.

    Snapshots the current profile on the coordinator so the matching stop
    service can restore it. Verifies every write by raw readback; on mismatch
    the profile is left untouched and HomeAssistantError is raised.
    """
    coordinator = entry.runtime_data
    client = coordinator.client

    # Snapshot before any write so a failed verify does not lose the original.
    if coordinator.nocturnal_cooling_prev_profile is None:
        coordinator.nocturnal_cooling_prev_profile = coordinator.data.profile

    await client.set_values(dict(_NOCTURNAL_COOLING_WRITES))
    await _async_verify_writes(coordinator, _NOCTURNAL_COOLING_WRITES)
    await client.set_profile(Profile.AWAY)
    await coordinator.async_request_refresh()


async def async_stop_nocturnal_cooling(entry: ValloxConfigEntry) -> None:
    """Revert the heating-season setpoint and Away target, restore the profile.

    Idempotent: a no-op if no cooling was started (no snapshotted profile).
    """
    coordinator = entry.runtime_data
    prev_profile = coordinator.nocturnal_cooling_prev_profile
    if prev_profile is None:
        return

    client = coordinator.client
    await client.set_values(dict(_NOCTURNAL_COOLING_RESTORE))
    await _async_verify_writes(coordinator, _NOCTURNAL_COOLING_RESTORE)
    await client.set_profile(prev_profile)
    coordinator.nocturnal_cooling_prev_profile = None
    await coordinator.async_request_refresh()


async def _async_start_nocturnal_cooling_call(call: ServiceCall) -> None:
    """Service wrapper for start_nocturnal_cooling."""
    await async_start_nocturnal_cooling(_get_entry(call.hass))


async def _async_stop_nocturnal_cooling_call(call: ServiceCall) -> None:
    """Service wrapper for stop_nocturnal_cooling."""
    await async_stop_nocturnal_cooling(_get_entry(call.hass))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Vallox services."""
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_AWAY,
        _async_set_profile_fan_speed_away,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_BOOST,
        _async_set_profile_fan_speed_boost,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE_FAN_SPEED_HOME,
        _async_set_profile_fan_speed_home,
        schema=SERVICE_SCHEMA_SET_PROFILE_FAN_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.SET_PROFILE,
        _async_set_profile,
        schema=SERVICE_SCHEMA_SET_PROFILE,
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.START_NOCTURNAL_COOLING,
        _async_start_nocturnal_cooling_call,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        ValloxService.STOP_NOCTURNAL_COOLING,
        _async_stop_nocturnal_cooling_call,
        schema=vol.Schema({}),
    )
