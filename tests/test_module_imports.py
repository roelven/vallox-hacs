"""Smoke test: every existing Vallox integration module imports on a released HA.

The scaffold was vendored from HA core `dev`, which is ahead of the latest
release. This test guards the compatibility shims (`from __future__ import
annotations` for forward-ref entity annotations, and the not-yet-released
`UnitOfRatio` enum) so the integration loads on a HA version users actually run.
"""

from __future__ import annotations

import importlib

import pytest

# Modules that already exist in the vendored scaffold. The new select platform
# is added in a later step and gets its own import test there.
EXISTING_PLATFORM_MODULES = (
    "binary_sensor",
    "config_flow",
    "const",
    "coordinator",
    "date",
    "entity",
    "fan",
    "number",
    "sensor",
    "services",
    "switch",
)


@pytest.mark.parametrize("module_name", EXISTING_PLATFORM_MODULES)
def test_module_imports(module_name: str) -> None:
    """Each existing integration module imports without error."""
    mod = importlib.import_module(f"custom_components.vallox.{module_name}")
    assert mod is not None


@pytest.mark.parametrize(
    "module_name",
    ("binary_sensor", "date", "fan", "number", "sensor", "switch"),
)
def test_platform_setup_entry_callable(module_name: str) -> None:
    """Each existing platform module exposes async_setup_entry."""
    mod = importlib.import_module(f"custom_components.vallox.{module_name}")
    assert callable(getattr(mod, "async_setup_entry", None)), (
        f"{module_name}.async_setup_entry missing"
    )