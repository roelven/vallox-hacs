"""Tests for the new constants added to const.py for the cooling extensions."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture(scope="module")
def const():
    return importlib.import_module("custom_components.vallox.const")


def test_adjust_mode_enum_maps(const) -> None:
    assert const.ADJUST_MODE_SUPPLY == 0
    assert const.ADJUST_MODE_EXTRACT == 1
    assert const.ADJUST_MODE_COOLING == 2
    assert const.ADJUST_MODE_TO_STR == {
        const.ADJUST_MODE_SUPPLY: "supply",
        const.ADJUST_MODE_EXTRACT: "extract",
        const.ADJUST_MODE_COOLING: "cooling",
    }
    # reverse map is the exact inverse
    assert const.ADJUST_MODE_STR_TO_VALUE == {
        v: k for k, v in const.ADJUST_MODE_TO_STR.items()
    }


def test_service_names(const) -> None:
    assert const.SERVICE_START_NOCTURNAL_COOLING == "start_nocturnal_cooling"
    assert const.SERVICE_STOP_NOCTURNAL_COOLING == "stop_nocturnal_cooling"


def test_cooling_register_keys_and_values(const) -> None:
    assert const.HEATING_SEASON_SETPOINT == "A_CYC_POST_HEATER_WINTER_SETPOINT"
    assert const.AWAY_AIR_TEMP_TARGET == "A_CYC_AWAY_AIR_TEMP_TARGET"
    # night (cooling) values
    assert const.COOLING_HEATING_SEASON_SETPOINT == 5.0
    assert const.COOLING_AWAY_TARGET == 8.0
    # commissioned (restored on stop) values
    assert const.COMMISSIONED_HEATING_SEASON_SETPOINT == 15.0
    assert const.COMMISSIONED_AWAY_TARGET == 20.0