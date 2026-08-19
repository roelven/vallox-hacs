"""Tests for manifest.json and hacs.json metadata required by HACS."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    return json.loads(
        (_repo_root() / "custom_components" / "vallox" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )


def _hacs() -> dict:
    return json.loads((_repo_root() / "hacs.json").read_text(encoding="utf-8"))


def test_manifest_required_keys() -> None:
    m = _manifest()
    for key in (
        "domain",
        "name",
        "version",
        "codeowners",
        "config_flow",
        "iot_class",
        "requirements",
    ):
        assert key in m, f"manifest missing {key}"
    assert m["domain"] == "vallox"
    assert m["config_flow"] is True


def test_manifest_pins_vallox_lib() -> None:
    requirements = _manifest()["requirements"]
    assert any(r.startswith("vallox-websocket-api==") for r in requirements), requirements


def test_manifest_iot_class_is_local_polling() -> None:
    # The unit is polled over the local network websocket; not cloud, not push.
    assert _manifest()["iot_class"] == "local_polling"


def test_manifest_version_is_semver() -> None:
    version = _manifest()["version"]
    assert version.count(".") == 2 and all(part.isdigit() for part in version.split(".")), (
        f"version {version} is not x.y.z"
    )


def test_hacs_json_has_name_and_min_ha() -> None:
    h = _hacs()
    assert h.get("name")
    assert h.get("render_readme") is True
    assert h.get("homeassistant"), "hacs.json must declare a minimum HA version"


def test_strings_and_en_translations_have_new_entity_keys() -> None:
    """The new entities/services are present in both strings and en translations."""
    base = _repo_root() / "custom_components" / "vallox"
    strings = json.loads((base / "strings.json").read_text(encoding="utf-8"))
    en = json.loads((base / "translations" / "en.json").read_text(encoding="utf-8"))

    expected_number_keys = {"heating_season_setpoint", "supply_air_defrost_temp"}
    assert expected_number_keys <= set(strings["entity"]["number"])
    assert expected_number_keys <= set(en["entity"]["number"])

    assert "supply_heating_adjust_mode" in strings["entity"]["select"]
    assert "supply_heating_adjust_mode" in en["entity"]["select"]

    for bs in ("in_bypass", "dewpoint_limit_in_use"):
        assert bs in strings["entity"]["binary_sensor"]
        assert bs in en["entity"]["binary_sensor"]

    for svc in ("start_nocturnal_cooling", "stop_nocturnal_cooling"):
        assert svc in strings["services"]
        assert svc in en["services"]


@pytest.mark.parametrize(
    "icon_section,key",
    [
        ("number", "heating_season_setpoint"),
        ("number", "supply_air_defrost_temp"),
        ("select", "supply_heating_adjust_mode"),
        ("binary_sensor", "in_bypass"),
        ("binary_sensor", "dewpoint_limit_in_use"),
    ],
)
def test_icons_defined_for_new_entities(icon_section, key) -> None:
    icons = json.loads(
        (_repo_root() / "custom_components" / "vallox" / "icons.json").read_text(encoding="utf-8")
    )
    assert icons["entity"][icon_section][key]["default"].startswith("mdi:")
