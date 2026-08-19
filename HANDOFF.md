# HANDOFF — build task list for the agent

This repo is a scaffolded fork of the Home Assistant Vallox integration. The
upstream files are already vendored under `custom_components/vallox/` (fetched
from `home-assistant/core` `dev` branch). The HACS boilerplate, license, i18n
strings (including the new entities/services), icons, blueprints, and test stubs
are in place. **Your job is to write the Python that makes the new entities and
services work.** Everything below is concrete.

## Authoritative references (read these first)

- `../vallox-logger/HA_INTEGRATION_SPEC.md` — *what* to add, with per-register
  rationale, ranges, writability evidence, and the rejected list. This is the
  source of truth for the entity set.
- `../vallox-logger/HA_AUTOMATION_PLAN.md` — the migration, testing, and the
  cooling-routine design (service contract, profile snapshot, safety gates).
- `../vallox-logger/INVESTIGATION.md` / `REPORT_FINAL_SOLUTION.md` /
  `FINDINGS.md` — the empirical evidence (which levers work, which were
  falsified, the centi-Kelvin encoding, the `BYPASS_LOCKED` one-direction
  behaviour, the readback-verification methodology).
- `../vallox-logger/vallox_raw.py` — the proven raw readback helper. Port its
  read path into the service's verification step.
- `../vallox-logger/archive/experiments/{h7_start,stack_start,cooling_mode_start,test_heating_season_writable}.py`
  — the reference scripts that prove each register is websocket-writable with
  exact readback. The service is these, ported into the integration.

## Critical facts (do not re-derive; these are verified)

- **Entity IDs come from the friendly name, not the translation key.** The
  upstream target entities are `number.vallox_supply_air_temperature_home`
  (name "Supply air temperature (Home)"), *not* `…_target_…`. Our new entities
  therefore resolve to:
  `number.vallox_heating_season_setpoint`, `number.vallox_supply_air_defrost_temp`,
  `select.vallox_supply_heating_adjust_mode`, `binary_sensor.vallox_in_bypass`,
  `binary_sensor.vallox_dewpoint_limit_in_use`. The `strings.json` /
  `translations/en.json` names already produce these. Keep the `key` values
  matching the translation keys already in `strings.json`.
- **Temperature registers are centi-Kelvin** (`raw/100 − 273.15`). The
  `vallox_websocket_api` library handles Celsius→centi-Kelvin conversion inside
  `client.set_values()` for known temperature metric keys — proven by the
  upstream number entities and by `h7_start.py` (writes `5.0`, raw readback
  verifies `5.00 °C`). So `number.set_value` passing a Celsius float works; do
  not convert manually on the write path.
- **`client.fetch_metrics()` returns 0 for centi-Kelvin registers on this
  firmware** (a known issue, documented in `../vallox-logger/vallox_raw.py`).
  For *readback verification* you must read the raw register table, not
  `fetch_metrics`. The coordinator already reads the raw table the same way the
  existing entities do, so the displayed `native_value` is correct — but for the
  service's verify step, use the raw table read (see `vallox_raw.read_raw`).
- **`A_CYC_POST_HEATER_WINTER_SETPOINT`**: addr 20554, default 15.0 °C, writable
  (write 14.0 → read 14.0; write 5.0 → read 5.00 °C). Proposed range 5.0–25.0
  step 1.0 (min proven; max to confirm on hardware).
- **`A_CYC_SUPPLY_AIR_DEFROST_TEMP`**: addr 20522, default 15.0 °C, firmware
  **min 10 °C** (writes below 10 are silently clamped — document this in the
  description). Proposed range 10.0–20.0 step 1.0.
- **`A_CYC_SUPPLY_HEATING_ADJUST_MODE`**: addr 20549, enum
  `0=Supply (C_CYC_HEATING_SUPPLY)`, `1=Extract (C_CYC_HEATING_EXTRACT)`,
  `2=Cooling (C_CYC_HEATING_COOLING)`, default 0, writable. This needs a **new
  `select.py` platform** (the integration has none today).
- **`A_CYC_DEWPOINT_LIMIT_IN_USE`**: addr 20555, read-only (touch-panel only,
  not websocket-settable). Expose as `binary_sensor` only — never as a switch.
- **`A_CYC_IN_BYPASS`**: addr 5126, read-only status flag (`on` ⇔ damper open).
- **Profile snapshot must NOT clobber `input_text.vallox_previous_profile`** —
  that helper is used by the existing KNX↔Vallox profile automations in the
  user's HA. Store the cooling snapshot in the config entry's runtime data
  (e.g. a dict on `entry.runtime_data`) or a dedicated slot, not a user-facing
  helper.
- **`switch.vallox_bypass_locked`** stays as upstream exposes it (ON = force
  heat-recovery / block bypass; OFF = release to automatic). Leave it OFF. Do
  not add a "force bypass open" entity — no register does that on this firmware
  (verified; see `FINDINGS.md`).

## Concrete code changes

### 1. `custom_components/vallox/const.py`

Add:

```python
# Heating-control mode (A_CYC_SUPPLY_HEATING_ADJUST_MODE) enum.
ADJUST_MODE_SUPPLY = 0
ADJUST_MODE_EXTRACT = 1
ADJUST_MODE_COOLING = 2
ADJUST_MODE_TO_STR = {ADJUST_MODE_SUPPLY: "supply",
                      ADJUST_MODE_EXTRACT: "extract",
                      ADJUST_MODE_COOLING: "cooling"}
ADJUST_MODE_STR_TO_VALUE = {v: k for k, v in ADJUST_MODE_TO_STR.items()}

# Nocturnal cooling service names + the values they write.
SERVICE_START_NOCTURNAL_COOLING = "start_nocturnal_cooling"
SERVICE_STOP_NOCTURNAL_COOLING = "stop_nocturnal_cooling"

HEATING_SEASON_SETPOINT = "A_CYC_POST_HEATER_WINTER_SETPOINT"
AWAY_AIR_TEMP_TARGET = "A_CYC_AWAY_AIR_TEMP_TARGET"
COOLING_HEATING_SEASON_SETPOINT = 5.0   # night value
COOLING_AWAY_TARGET = 8.0                # night value
COMMISSIONED_HEATING_SEASON_SETPOINT = 15.0
COMMISSIONED_AWAY_TARGET = 20.0
```

### 2. `custom_components/vallox/__init__.py`

Add `Platform.SELECT` to the `PLATFORMS` list so the new select platform loads.

### 3. `custom_components/vallox/number.py`

Append two `ValloxNumberEntityDescription`s to `NUMBER_ENTITIES`:

```python
ValloxNumberEntityDescription(
    key="heating_season_setpoint",
    translation_key="heating_season_setpoint",
    metric_key="A_CYC_POST_HEATER_WINTER_SETPOINT",
    device_class=NumberDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    native_min_value=5.0,
    native_max_value=25.0,
    native_step=1.0,
),
ValloxNumberEntityDescription(
    key="supply_air_defrost_temp",
    translation_key="supply_air_defrost_temp",
    metric_key="A_CYC_SUPPLY_AIR_DEFROST_TEMP",
    device_class=NumberDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    native_min_value=10.0,   # firmware enforces min 10
    native_max_value=20.0,
    native_step=1.0,
),
```

### 4. `custom_components/vallox/select.py` (NEW)

A generic Vallox select platform. Pattern:

```python
from dataclasses import dataclass
from typing import override
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .const import ADJUST_MODE_STR_TO_VALUE, ADJUST_MODE_TO_STR
from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .entity import ValloxEntity

@dataclass(frozen=True, kw_only=True)
class ValloxSelectEntityDescription(SelectEntityDescription):
    metric_key: str
    options_map: dict[int, str]
    reverse_map: dict[str, int]

class ValloxSelectEntity(ValloxEntity, SelectEntity):
    _attr_entity_category = ...  # EntityCategory.CONFIG
    entity_description: ValloxSelectEntityDescription

    def __init__(self, name, coordinator, description):
        super().__init__(name, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._attr_options = list(description.options_map.values())

    @property
    @override
    def current_option(self) -> str | None:
        if (v := self.coordinator.data.get(self.entity_description.metric_key)) is None:
            return None
        return self.entity_description.options_map.get(int(v))

    @override
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.set_values(
            {self.entity_description.metric_key: self.entity_description.reverse_map[option]}
        )
        await self.coordinator.async_request_refresh()

SELECT_ENTITIES = (
    ValloxSelectEntityDescription(
        key="supply_heating_adjust_mode",
        translation_key="supply_heating_adjust_mode",
        metric_key="A_CYC_SUPPLY_HEATING_ADJUST_MODE",
        options_map=ADJUST_MODE_TO_STR,
        reverse_map=ADJUST_MODE_STR_TO_VALUE,
    ),
)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        ValloxSelectEntity(entry.data[CONF_NAME], coordinator, d) for d in SELECT_ENTITIES
    )
```

### 5. `custom_components/vallox/binary_sensor.py`

Add two `ValloxBinarySensorEntityDescription`s for `A_CYC_IN_BYPASS` and
`A_CYC_DEWPOINT_LIMIT_IN_USE` (`is_on ⇔ value == 1`). `in_bypass` category
`diagnostic`; `dewpoint_limit_in_use` category `diagnostic`.

### 6. `custom_components/vallox/services.py`

Extend the existing `async_setup_services(hass)` to register
`start_nocturnal_cooling` and `stop_nocturnal_cooling`. The implementation must:

1. **Snapshot** the current profile into `entry.runtime_data` under a dedicated
   key (e.g. `entry.runtime_data.nocturnal_cooling_prev_profile`) — NOT a
   user-facing helper.
2. **Write** the register values via `client.set_values()`:
   - start: `{HEATING_SEASON_SETPOINT: COOLING_HEATING_SEASON_SETPOINT,
              AWAY_AIR_TEMP_TARGET: COOLING_AWAY_TARGET}` then
     `client.set_profile(Profile.AWAY)`.
   - stop: reverse the two register writes, then `client.set_profile(prev)`.
3. **Verify by raw readback** — read the raw register table (port
   `../vallox-logger/vallox_raw.py`'s `read_raw` approach: build a
   `read_table_request`, parse the response, look up the metric's address via
   `client.data_model.addresses` and its offset) and compare the converted
   Celsius to the written value. On mismatch raise `HomeAssistantError` using
   the `nocturnal_cooling_verify_failed` exception (already in `strings.json`).
4. **Idempotency**: `stop_nocturnal_cooling` is a no-op (or a commissioned-baseline
   restore) if no cooling was started.

### 7. `custom_components/vallox/services.yaml`

Add the two service schemas (no fields):

```yaml
start_nocturnal_cooling:
  name: Start nocturnal cooling
  description: >
    Lowers the heating-season setpoint so the unit keeps the bypass open on a
    cool summer night, sets the Away profile supply-air target to 8 °C, and
    switches the unit to the Away profile. Snapshots the current profile so
    stop_nocturnal_cooling can restore it. Verifies every write by raw readback.
stop_nocturnal_cooling:
  name: Stop nocturnal cooling
  description: >
    Reverts the heating-season setpoint to 15 °C, the Away target to 20 °C, and
    restores the profile snapshotted by start_nocturnal_cooling. Idempotent.
```

### 8. `custom_components/vallox/icons.json`

Add icons for the new entities/services (e.g. `heating_season_setpoint` →
`mdi:thermostat`, `supply_air_defrost_temp` → `mdi:snowflake`,
`supply_heating_adjust_mode` → `mdi:tune`, `in_bypass` → `mdi:swap-horizontal`,
`dewpoint_limit_in_use` → `mdi:water-percent`,
`start_nocturnal_cooling`/`stop_nocturnal_cooling` → `mdi:weather-night` /
`mdi:weather-sunny`).

### 9. Tests (`tests/`)

- `test_entity_descriptions.py` — assert the new `NUMBER_ENTITIES` /
  `SELECT_ENTITIES` / binary_sensor descriptions have the expected metric keys,
  keys, and ranges.
- `test_readback_conversion.py` — centi-Kelvin ↔ Celsius round-trip and sentinel
  handling (0 and 0xFFFF → None), mirroring `vallox_raw.to_c`.
- `test_services.py` — mock `Vallox` client; assert start writes the right
  values and readback-matches, stop reverts, stop-without-start is a no-op, and
  a readback mismatch raises.

## Migration & testing (no second VM)

- The production HA is at `192.168.20.7:8123`. The Vallox unit is at
  `192.168.20.172`, firmware 3.1.6. The user has a solid HA backup strategy.
- Install this fork over the built-in (same `vallox` domain), restart. The
  existing config entry re-initialises; entity IDs are preserved (verified the
  live entities in `../vallox-logger/HA_AUTOMATION_PLAN.md` §2). **Do not**
  delete the existing config entry.
- The raw logger `../vallox-logger/collector.py` (still running on the
  non-persistent VM while it lives) captures the full register table every 60 s.
  On the first test night, confirm in `~/vallox-logs/*.jsonl` that
  `A_CYC_POST_HEATER_WINTER_SETPOINT` read back 5.0, the profile flipped to
  Away, and `A_CYC_CELL_STATE` went to BYPASS below 15.7 °C.
- Confirm ranges on hardware before release: H7 max (propose 25), defrost max
  (propose 20), and that all three adjust-mode options are accepted.

## Out of scope (do not add)

- `A_CYC_BYPASS_LOCKED` (already exposed; misleading name is a docs issue, not a
  new-entity issue; it can only block bypass, never compel it).
- `A_CYC_PARTIAL_BYPASS` / `A_CYC_PARTIAL_BYPASS_DISABLED` (inert on this model).
- `A_CYC_MLV_SUPPLY_LOWER_LIMIT` (falsified as a live clamp).
- `A_CYC_DEWPOINT_LIMIT_IN_USE` as a switch (not writable — read-only only).
- `A_CYC_MLV_WINTER_SETPOINT` (a different 2 °C register; if ever added, name it
  "MLV winter setpoint" to avoid colliding with `heating_season_setpoint`).

## Upstream

Once the `heating_season_setpoint` number + the two services are proven in
production, submit the minimal subset to `home-assistant/core`. Keep this fork's
diff as "upstream + our additions" so it can collapse back when the PR merges.