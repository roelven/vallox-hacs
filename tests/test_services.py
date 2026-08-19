"""Tests for the start/stop_nocturnal_cooling service against a mocked client.

These define the contract the implementation in services.py must satisfy:
  * start writes H7=5 + Away target=8, switches to Away, and readback-verifies;
  * stop reverts H7=15 + Away target=20 and restores the snapshotted profile;
  * stop without a prior start is a no-op (or a commissioned restore);
  * a readback mismatch raises.

The actual verification read path should use the raw register table read (not
client.fetch_metrics, which returns 0 for centi-Kelvin registers on this
firmware). Mock both client.set_values and the raw readback helper.
"""

import pytest


class FakeVallox:
    """Minimal stand-in for vallox_websocket_api.Vallox."""

    def __init__(self):
        self.written = {}
        self._raw = {}          # metric_key -> raw centi-Kelvin int (or int)
        self.profile = "Home"
        self._profiles_set = []

    async def set_values(self, mapping):
        self.written.update(mapping)

    async def set_profile(self, profile):
        self.profile = profile
        self._profiles_set.append(profile)

    async def read_raw(self, keys):
        return dict(self._raw)


def _set_raw(fake, key, celsius):
    fake._raw[key] = int(round((celsius + 273.15) * 100))


# NOTE: import the real async_setup_services once services.py implements it.
# Until then, these tests document the expected behaviour and are skipped.

pytestmark = pytest.mark.skip(reason="services.py not yet implemented")


def test_start_writes_and_verifies():
    fake = FakeVallox()
    _set_raw(fake, "A_CYC_POST_HEATER_WINTER_SETPOINT", 5.0)
    _set_raw(fake, "A_CYC_AWAY_AIR_TEMP_TARGET", 8.0)
    # expect: written {H7: 5.0, AWAY_TARGET: 8.0}, set_profile(Away), readback ok


def test_stop_reverts_and_restores_profile():
    fake = FakeVallox()
    # after a start with prev_profile=Home:
    # expect: written {H7: 15.0, AWAY_TARGET: 20.0}, set_profile(Home)


def test_stop_without_start_is_noop():
    fake = FakeVallox()
    # expect: no writes, no profile change


def test_readback_mismatch_raises():
    fake = FakeVallox()
    _set_raw(fake, "A_CYC_POST_HEATER_WINTER_SETPOINT", 15.0)  # didn't take
    # expect: HomeAssistantError via nocturnal_cooling_verify_failed