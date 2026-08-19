"""Tests for the extended Vallox entity descriptions.

Asserts the new number/select/binary_sensor descriptions carry the expected
metric keys, keys, and ranges. Pure-logic: no HA runtime needed.
"""

import importlib

import pytest


@pytest.fixture(scope="module")
def number_module():
    return importlib.import_module("custom_components.vallox.number")


@pytest.fixture(scope="module")
def select_module():
    return importlib.import_module("custom_components.vallox.select")


def _by_key(descs, key):
    return next(d for d in descs if d.key == key)


def test_heating_season_setpoint_description(number_module):
    d = _by_key(number_module.NUMBER_ENTITIES, "heating_season_setpoint")
    assert d.metric_key == "A_CYC_POST_HEATER_WINTER_SETPOINT"
    assert d.native_min_value == 5.0
    assert d.native_max_value == 25.0
    assert d.native_step == 1.0
    assert d.translation_key == "heating_season_setpoint"


def test_supply_air_defrost_temp_description(number_module):
    d = _by_key(number_module.NUMBER_ENTITIES, "supply_air_defrost_temp")
    assert d.metric_key == "A_CYC_SUPPLY_AIR_DEFROST_TEMP"
    assert d.native_min_value == 10.0  # firmware enforces min 10
    assert d.translation_key == "supply_air_defrost_temp"


def test_supply_heating_adjust_mode_select(select_module):
    d = _by_key(select_module.SELECT_ENTITIES, "supply_heating_adjust_mode")
    assert d.metric_key == "A_CYC_SUPPLY_HEATING_ADJUST_MODE"
    assert set(d.options_map.values()) == {"supply", "extract", "cooling"}
    assert d.reverse_map["cooling"] == 2