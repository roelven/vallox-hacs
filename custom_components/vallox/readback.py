"""Raw register readback helpers for write verification.

`vallox_websocket_api.Vallox.fetch_metric_data` returns 0 for centi-Kelvin
registers (temperatures and temperature setpoints) on this firmware, so it
cannot be used to confirm a write. The coordinator reads the raw register
table the same way the existing entities do, but for the nocturnal-cooling
service's verify step we read the raw table directly and convert centi-Kelvin
to Celsius ourselves.

Ported from ../vallox-logger/vallox_raw.py (proven against a ValloPlus 350 MV,
firmware 3.1.6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vallox_websocket_api import Vallox

if TYPE_CHECKING:
    from collections.abc import Iterable

# Sentinel raw values the firmware uses to mean "no reading".
_RAW_SENTINELS = (0, 0xFFFF)


def to_c(raw: int | None) -> float | None:
    """Convert a centi-Kelvin raw register value to Celsius.

    Returns None for missing data or the 0 / 0xFFFF sentinels.
    """
    if raw is None or raw in _RAW_SENTINELS:
        return None
    return round(raw / 100 - 273.15, 2)


async def read_raw(client: Vallox, keys: Iterable[str]) -> dict[str, int | None]:
    """Read raw register values for the given metric keys via the table read.

    Returns a mapping of metric key to raw integer (or None if the key is
    unknown or absent from the table). Uses the same read_table_request /
    read_table_response path as the raw logger, not fetch_metric_data.
    """
    await client.load_data_model()

    payload = client.messages.read_table_request.build({})
    result = await client._websocket_request(payload)
    data = client.messages.read_table_response.parse(result)

    out: dict[str, int | None] = {}
    for key in keys:
        addr = client.data_model.addresses.get(key)
        if addr is None:
            out[key] = None
            continue
        offset = client.data_model.calculate_offset(addr)
        if offset is None:
            out[key] = None
            continue
        try:
            out[key] = int(data[offset])
        except IndexError:
            out[key] = None
    return out
