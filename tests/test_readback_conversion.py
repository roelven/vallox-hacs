"""Tests for the centi-Kelvin <-> Celsius readback conversion used by the
nocturnal-cooling service verification step.

Exercises the real implementation in custom_components.vallox.readback, which
mirrors ../vallox-logger/vallox_raw.py: raw/100 - 273.15, with sentinels 0 and
0xFFFF meaning "no reading".
"""

from __future__ import annotations

import pytest

from custom_components.vallox.readback import to_c

RAW_FREEZING = 27315  # 0.00 C
RAW_5C = 27815  # 5.00 C
RAW_15C = 28815  # 15.00 C
RAW_20C = 29315  # 20.00 C
RAW_8C = 28115  # 8.00 C


def test_known_points() -> None:
    assert to_c(RAW_5C) == 5.00
    assert to_c(RAW_15C) == 15.00
    assert to_c(RAW_20C) == 20.00
    assert to_c(RAW_8C) == 8.00
    assert to_c(RAW_FREEZING) == 0.00


@pytest.mark.parametrize("sentinel", [None, 0, 65535])
def test_sentinels_are_none(sentinel) -> None:
    assert to_c(sentinel) is None
