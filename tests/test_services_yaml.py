"""Tests for services.yaml and the service-registration contract.

Ensures the two nocturnal-cooling services are declared in services.yaml with no
fields, and that the service schema registered in services.py accepts an empty
call (no fields). Pure-data: no HA runtime needed.
"""

from __future__ import annotations

from pathlib import Path

import voluptuous as vol
import yaml


def _services_yaml() -> str:
    path = Path(__file__).resolve().parents[1] / "custom_components" / "vallox" / "services.yaml"
    return path.read_text(encoding="utf-8")


def test_nocturnal_cooling_services_declared() -> None:
    data = yaml.safe_load(_services_yaml())
    assert "start_nocturnal_cooling" in data
    assert "stop_nocturnal_cooling" in data


def test_nocturnal_cooling_services_have_no_fields() -> None:
    data = yaml.safe_load(_services_yaml())
    for svc in ("start_nocturnal_cooling", "stop_nocturnal_cooling"):
        # Either no "fields" key at all, or an empty fields mapping.
        assert not data[svc].get("fields"), f"{svc} must not declare fields"


def test_nocturnal_cooling_schema_accepts_empty() -> None:
    """The schema registered for each nocturnal cooling service accepts no fields."""
    from custom_components.vallox import services

    registered: dict[str, vol.Schema] = {}

    class FakeServices:
        def async_register(self, _domain, name, _handler, schema):
            registered[name] = schema

    class FakeHass:
        services = FakeServices()

    services.async_setup_services(FakeHass())  # type: ignore[arg-type]
    for svc in ("start_nocturnal_cooling", "stop_nocturnal_cooling"):
        assert svc in registered, f"{svc} not registered"
        # An empty data dict must validate (no fields required).
        assert registered[svc]({}) == {}


def test_service_names_match_const() -> None:
    from custom_components.vallox.const import (
        SERVICE_START_NOCTURNAL_COOLING,
        SERVICE_STOP_NOCTURNAL_COOLING,
    )

    data = yaml.safe_load(_services_yaml())
    assert SERVICE_START_NOCTURNAL_COOLING in data
    assert SERVICE_STOP_NOCTURNAL_COOLING in data


def test_coordinator_has_snapshot_attribute_default() -> None:
    """The coordinator exposes a default-None profile snapshot slot."""
    from custom_components.vallox.coordinator import ValloxDataUpdateCoordinator

    assert ValloxDataUpdateCoordinator.nocturnal_cooling_prev_profile is None
