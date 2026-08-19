"""Tests for the extended Vallox entity descriptions.

Asserts the new number/select/binary_sensor descriptions carry the expected
metric keys, keys, and ranges. Pure-logic: no HA runtime needed.
"""

from __future__ import annotations

import importlib

from homeassistant.const import EntityCategory
import pytest


@pytest.fixture(scope="module")
def number_module():
    return importlib.import_module("custom_components.vallox.number")


@pytest.fixture(scope="module")
def select_module():
    return importlib.import_module("custom_components.vallox.select")


@pytest.fixture(scope="module")
def binary_sensor_module():
    return importlib.import_module("custom_components.vallox.binary_sensor")


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


def test_in_bypass_description(binary_sensor_module):
    d = _by_key(binary_sensor_module.BINARY_SENSOR_ENTITIES, "in_bypass")
    assert d.metric_key == "A_CYC_IN_BYPASS"
    assert d.translation_key == "in_bypass"
    assert d.entity_category is EntityCategory.DIAGNOSTIC


def test_dewpoint_limit_in_use_description(binary_sensor_module):
    d = _by_key(binary_sensor_module.BINARY_SENSOR_ENTITIES, "dewpoint_limit_in_use")
    assert d.metric_key == "A_CYC_DEWPOINT_LIMIT_IN_USE"
    assert d.translation_key == "dewpoint_limit_in_use"
    assert d.entity_category is EntityCategory.DIAGNOSTIC
