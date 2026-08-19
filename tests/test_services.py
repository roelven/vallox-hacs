"""Tests for the start/stop_nocturnal_cooling service against a mocked client.

These define the contract the implementation in services.py must satisfy:
  * start writes H7=5 + Away target=8, verifies by raw readback, switches to Away,
    and snapshots the current profile on the coordinator;
  * stop reverts H7=15 + Away target=20, verifies, and restores the snapshotted
    profile, then clears the snapshot;
  * stop without a prior start is a no-op;
  * a readback mismatch raises HomeAssistantError with
    nocturnal_cooling_verify_failed.

The raw read path (services.read_raw) is monkeypatched so no network is touched.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from vallox_websocket_api import Profile

from custom_components.vallox import services
from custom_components.vallox.const import (
    AWAY_AIR_TEMP_TARGET,
    COMMISSIONED_AWAY_TARGET,
    COMMISSIONED_HEATING_SEASON_SETPOINT,
    COOLING_AWAY_TARGET,
    COOLING_HEATING_SEASON_SETPOINT,
    HEATING_SEASON_SETPOINT,
)
from custom_components.vallox.coordinator import ValloxDataUpdateCoordinator


class FakeMetricData:
    """Stand-in for vallox_websocket_api.MetricData with .profile and .get()."""

    def __init__(self, profile: Profile) -> None:
        self._profile = profile

    @property
    def profile(self) -> Profile:
        return self._profile

    def get(self, _key: str, default: Any = None) -> Any:
        return default


def _make_coordinator(fake_client: MagicMock, profile: Profile) -> ValloxDataUpdateCoordinator:
    """Build a minimal coordinator wired to the fake client."""
    coord = ValloxDataUpdateCoordinator.__new__(ValloxDataUpdateCoordinator)
    coord.client = fake_client
    coord.data = FakeMetricData(profile)
    coord.nocturnal_cooling_prev_profile = None
    coord.async_request_refresh = AsyncMock()  # type: ignore[method-assign]
    return coord


def _make_entry(coord: ValloxDataUpdateCoordinator) -> MagicMock:
    entry = MagicMock()
    entry.runtime_data = coord
    return entry


def _set_raw(raw_map: dict[str, int | None], key: str, celsius: float) -> None:
    raw_map[key] = int(round((celsius + 273.15) * 100))


def _patch_read_raw(monkeypatch, raw_map: dict[str, int | None]) -> None:
    """Make services.read_raw return the provided raw map."""

    async def _fake_read_raw(_client, keys):
        return {k: raw_map.get(k) for k in keys}

    monkeypatch.setattr(services, "read_raw", _fake_read_raw)


@pytest.mark.parametrize("start_profile", [Profile.HOME, Profile.AUTO])
async def test_start_writes_verifies_and_snapshots(start_profile, monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.set_values = AsyncMock()
    fake_client.set_profile = AsyncMock()

    coord = _make_coordinator(fake_client, start_profile)
    entry = _make_entry(coord)

    raw: dict[str, int | None] = {}
    _set_raw(raw, HEATING_SEASON_SETPOINT, COOLING_HEATING_SEASON_SETPOINT)
    _set_raw(raw, AWAY_AIR_TEMP_TARGET, COOLING_AWAY_TARGET)
    _patch_read_raw(monkeypatch, raw)

    await services.async_start_nocturnal_cooling(entry)

    fake_client.set_values.assert_awaited()
    written = fake_client.set_values.await_args.args[0]
    assert written == {
        HEATING_SEASON_SETPOINT: COOLING_HEATING_SEASON_SETPOINT,
        AWAY_AIR_TEMP_TARGET: COOLING_AWAY_TARGET,
    }
    fake_client.set_profile.assert_awaited_once_with(Profile.AWAY)
    assert coord.nocturnal_cooling_prev_profile is start_profile
    coord.async_request_refresh.assert_awaited()


async def test_stop_reverts_verifies_and_restores(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.set_values = AsyncMock()
    fake_client.set_profile = AsyncMock()

    coord = _make_coordinator(fake_client, Profile.AWAY)
    coord.nocturnal_cooling_prev_profile = Profile.HOME  # snapshotted by a prior start
    entry = _make_entry(coord)

    raw: dict[str, int | None] = {}
    _set_raw(raw, HEATING_SEASON_SETPOINT, COMMISSIONED_HEATING_SEASON_SETPOINT)
    _set_raw(raw, AWAY_AIR_TEMP_TARGET, COMMISSIONED_AWAY_TARGET)
    _patch_read_raw(monkeypatch, raw)

    await services.async_stop_nocturnal_cooling(entry)

    written = fake_client.set_values.await_args.args[0]
    assert written == {
        HEATING_SEASON_SETPOINT: COMMISSIONED_HEATING_SEASON_SETPOINT,
        AWAY_AIR_TEMP_TARGET: COMMISSIONED_AWAY_TARGET,
    }
    fake_client.set_profile.assert_awaited_once_with(Profile.HOME)
    assert coord.nocturnal_cooling_prev_profile is None
    coord.async_request_refresh.assert_awaited()


async def test_stop_without_start_is_noop(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.set_values = AsyncMock()
    fake_client.set_profile = AsyncMock()

    coord = _make_coordinator(fake_client, Profile.HOME)
    entry = _make_entry(coord)

    await services.async_stop_nocturnal_cooling(entry)

    fake_client.set_values.assert_not_awaited()
    fake_client.set_profile.assert_not_awaited()
    coord.async_request_refresh.assert_not_awaited()


async def test_readback_mismatch_raises(monkeypatch) -> None:
    from homeassistant.exceptions import HomeAssistantError

    fake_client = MagicMock()
    fake_client.set_values = AsyncMock()
    fake_client.set_profile = AsyncMock()

    coord = _make_coordinator(fake_client, Profile.HOME)
    entry = _make_entry(coord)

    # The write "didn't take": H7 read back as 15 C instead of 5 C.
    raw: dict[str, int | None] = {}
    _set_raw(raw, HEATING_SEASON_SETPOINT, COMMISSIONED_HEATING_SEASON_SETPOINT)
    _set_raw(raw, AWAY_AIR_TEMP_TARGET, COOLING_AWAY_TARGET)
    _patch_read_raw(monkeypatch, raw)

    with pytest.raises(HomeAssistantError) as exc:
        await services.async_start_nocturnal_cooling(entry)

    assert exc.value.translation_key == "nocturnal_cooling_verify_failed"
    # The profile must not have been switched when verification failed.
    fake_client.set_profile.assert_not_awaited()