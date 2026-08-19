"""Smoke test: every existing Vallox integration module imports on a released HA.

The scaffold was vendored from HA core `dev`, which is ahead of the latest
release. This test guards the compatibility shims (`from __future__ import
annotations` for forward-ref entity annotations, and the not-yet-released
`UnitOfRatio` enum) so the integration loads on a HA version users actually run.
"""

from __future__ import annotations

import importlib

import pytest

# All integration modules, including the new select platform.
PLATFORM_MODULES = (
    "binary_sensor",
    "config_flow",
    "const",
    "coordinator",
    "date",
    "entity",
    "fan",
    "number",
    "select",
    "sensor",
    "services",
    "switch",
)


@pytest.mark.parametrize("module_name", PLATFORM_MODULES)
def test_module_imports(module_name: str) -> None:
    """Each integration module imports without error."""
    mod = importlib.import_module(f"custom_components.vallox.{module_name}")
    assert mod is not None


def test_init_platforms_include_select() -> None:
    """The new select platform must be registered in __init__.PLATFORMS."""
    init = importlib.import_module("custom_components.vallox.__init__")
    from homeassistant.const import Platform

    assert Platform.SELECT in init.PLATFORMS


@pytest.mark.parametrize(
    "module_name",
    ("binary_sensor", "date", "fan", "number", "select", "sensor", "switch"),
)
def test_platform_setup_entry_callable(module_name: str) -> None:
    """Each platform module exposes async_setup_entry."""
    mod = importlib.import_module(f"custom_components.vallox.{module_name}")
    assert callable(getattr(mod, "async_setup_entry", None)), (
        f"{module_name}.async_setup_entry missing"
    )
