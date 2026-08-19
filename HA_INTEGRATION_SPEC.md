# Spec: extend the Home Assistant Vallox integration with the heating-season / cooling registers

**Target:** `homeassistant/components/vallox/` (and its `strings.json` / `translations/en.json`).
**Source of evidence:** the sister repository's investigation (`../vallox-logger/INVESTIGATION.md`,
`../vallox-logger/REPORT_FINAL_SOLUTION.md`, `../vallox-logger/FINDINGS.md`, `../vallox-logger/schema*.json`), all verified against raw
register readback on a ValloPlus 350 MV, firmware 3.1.6.

## 1. Why this spec exists

The official Vallox integration exposes the three per-profile supply-air
temperature targets and the fan (preset + speed) — but it does **not** expose the
one register that decides whether the unit cools the house at night or warms it:
`A_CYC_POST_HEATER_WINTER_SETPOINT`. Without that lever there is no way to make
the unit stop fighting the floor cooling on a 9–15 °C summer night. This spec
proposes adding it, plus a small set of related registers that are currently
invisible or non-addressable from HA.

## 2. What the integration exposes today

Confirmed against the `dev` branch of `home-assistant/core`:

| Platform | Entity | Metric key | Settable? |
|---|---|---|---|
| `number` | `supply_air_target_home` | `A_CYC_HOME_AIR_TEMP_TARGET` | yes (5–25 °C) |
| `number` | `supply_air_target_away` | `A_CYC_AWAY_AIR_TEMP_TARGET` | yes (5–25 °C) |
| `number` | `supply_air_target_boost` | `A_CYC_BOOST_AIR_TEMP_TARGET` | yes (5–25 °C) |
| `fan` | (the unit) | profile + fan speed | yes (preset + %) |
| `switch` | `bypass_locked` | `A_CYC_BYPASS_LOCKED` | yes (0/1) |
| `binary_sensor` | `post_heater` | `A_CYC_IO_HEATER` | read-only |
| `sensor` | `cell_state`, temps, fan speeds, efficiency, filter date | various | read-only |
| service | `set_profile`, `set_profile_fan_speed_{home,away,boost}` | — | yes |

**The gap:** the seasonal / frost / mode registers below are all present in the
unit's data model and (where marked) websocket-writable, but none are exposed.

## 3. Proposed additions

Priority tiers: **P0** ship it; **P1** ship after verifying ranges on hardware;
**P2** read-only visibility, low risk; **optional** semantics uncertain, needs a
writability probe before exposing as settable.

### P0 — `number.vallox_heating_season_setpoint`  (the reason for this spec)

| | |
|---|---|
| Metric key | `A_CYC_POST_HEATER_WINTER_SETPOINT` |
| Address | 20554 |
| Device class | `NumberDeviceClass.TEMPERATURE` |
| Unit | `UnitOfTemperature.CELSIUS` |
| Min / max / step | `5.0` / `25.0` / `1.0` *(min proven at 5.0; confirm upper bound on hardware)* |
| Default (commissioned) | 15.0 °C (raw 28815, centi-Kelvin) |
| Writable | **Yes** — verified by raw readback (`test_heating_season_writable.py`: write 14.0 → read 14.0; `h7_start.py`: write 5.0 → read 5.00 °C) |
| Entity category | `config` |

**Entity description**

```python
(
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
)
```

`strings.json`:

```json
"heating_season_setpoint": {
  "name": "Heating season setpoint"
}
```

**What it does (user-facing description).** This is the outdoor-air temperature
below which the unit treats the season as "winter": it closes the bypass damper
and runs heat recovery (and, if fitted, the post-heater) to warm the incoming air
toward the supply-air target. Above this threshold the unit is free to bypass
the exchanger and deliver near-outdoor-temperature air. On a ValloPlus 350 MV
the default cutoff this produces is ~`setpoint + 0.7 °C` of hysteresis
(empirically ~15.7 °C at the 15 °C default).

**When should a user modify it?** Two legitimate cases:

1. **Nocturnal summer cooling in a climate where outdoor drops to ~9–15 °C at
   night.** Lowering it to 5 °C for the cooling window keeps the bypass engaged
   through the cold hours so the MVHR purges heat instead of tempering the supply
   back up to ~21 °C. This should be done by an automation that **reverts it
   before morning** (the 5 °C value is wrong for the heating season).
2. **Tuning the spring/autumn switchover** if the default 15 °C feels too eager or
   too reluctant for your climate.

**Why is there no alternative today?** This is the decisive finding of the
underlying investigation. Every other candidate lever was tested and falsified:

- The per-profile supply-air targets (already exposed) do **not** move the
  cutoff — tested at 5, 12, and 20 °C, cutoff stayed ~15.7 °C (H2 falsified).
- `A_CYC_SUPPLY_AIR_DEFROST_TEMP` was hypothesised to be the cutoff; lowering it
  15 → 10 °C left the cutoff at 15.7 °C (H3 falsified). It is a frost-protection
  setting, not the bypass gate (see P1 below).
- `A_CYC_BYPASS_LOCKED` (already exposed as `switch.bypass_locked`) can only
  *block* bypass (force heat recovery); it cannot *compel* bypass. Setting it to
  OFF is a no-op when the automatic logic already wants heat recovery.
- The profile system cannot carry this register — there is a single global
  `A_CYC_POST_HEATER_WINTER_SETPOINT`, no HOME/AWAY/BOOST variant.

So lowering this register is the **only** verified way to make the unit choose
bypass on a cold summer night. Exposing it in HA is what makes a robust,
reverting automation possible without an external script or sidecar.

**Safety note for the docs.** A low value left in place through the heating
season will cause the unit to under-recover heat (and run the post-heater hard)
all winter. Any automation that lowers this **must** revert it (e.g. by morning,
and on HA restart). The integration should not try to enforce this — it's an
automation concern — but the entity description and docs should say so plainly.

---

### P1 — `select.vallox_supply_heating_adjust_mode`

| | |
|---|---|
| Metric key | `A_CYC_SUPPLY_HEATING_ADJUST_MODE` |
| Address | 20549 |
| Options | `Supply` (0, `C_CYC_HEATING_SUPPLY`), `Extract` (1, `C_CYC_HEATING_EXTRACT`), `Cooling` (2, `C_CYC_HEATING_COOLING`) |
| Default | `Supply` (raw 0) |
| Writable | **Yes** — written by `cooling_mode_start.py` / `test_heating_adjust_mode.py` via `set_values` |
| Entity category | `config` |

This needs the integration to gain a small `select.py` platform (it has none
today) with a `ValloxSelectEntityDescription` carrying `metric_key` + an
`options_map: dict[int, str]`. `async_set_native_value` would map the option
string back to its int and call `client.set_values({metric_key: int_value})`;
`native_value` maps the current int to the option string. (Pattern is generic and
unlocks any future enum register.)

**What it does.** Selects which temperature the unit uses as the control
reference for the supply-air tempering loop: the supply-air sensor (`Supply`,
default), the extract-air sensor (`Extract`), or the manufacturer's packaged
"summer cooling" mode (`Cooling`). Per the Vallox firmware changelog
(v1.8.5/v2.0.2): *"Cell bypass is now more aggressive when temperature control
method is extract air or summer cooling."*

**When should a user modify it?** Set to `Cooling` for the cooling season if you
want the unit's built-in summer behaviour (more aggressive bypass) instead of
driving it manually via the P0 setpoint. `Extract` is useful if your supply
sensor placement is unreliable and you'd rather govern tempering by room
(extract) temperature.

**Why is there no alternative today?** This is the manufacturer's *designed*
summer-cooling switch, but it is not exposed anywhere in HA. Today the only way
to set it is the touch panel or a raw websocket write. **Honesty caveat for the
description:** on this specific firmware the effect of `Cooling` mode on the
bypass cutoff was *not* independently verified — the investigation found the P0
setpoint lever first and stopped. The description should say the mode is the
manufacturer-documented summer mode, not promise a specific cutoff shift.

---

### P1 — `number.vallox_supply_air_defrost_temp`

| | |
|---|---|
| Metric key | `A_CYC_SUPPLY_AIR_DEFROST_TEMP` |
| Address | 20522 |
| Device class | `NumberDeviceClass.TEMPERATURE` |
| Unit | `UnitOfTemperature.CELSIUS` |
| Min / max / step | `10.0` / `20.0` / `1.0` *(firmware enforces a hard min of 10 °C — writes below 10 are silently clamped; max to confirm on hardware)* |
| Default | 15.0 °C |
| Writable | **Yes** — written by `stack_start.py` (15 → 10, read back 10) |
| Entity category | `config` |

**What it does.** The supply-air temperature at which the unit activates
supply-air frost protection (defrost): it temporarily reduces or stops the
supply fan / modulates the damper to keep the cell from freezing. It is a
**winter freeze-protection threshold**, not a cooling control.

**When should a user modify it?** Rarely. Only to tune frost-protection
aggressiveness for your ducting and climate — e.g. lower it slightly if defrost
cycles are cutting off ventilation too eagerly in a mild winter; raise it if
you have exposed duct runs that risk freezing. **Do not lower it expecting a
cooling effect:** the investigation falsified the hypothesis that this register
sets the bypass cutoff (H3, falsified — cutoff stayed 15.7 °C when this was
moved 15 → 10). The description must state this explicitly so users are not
tempted to misuse it.

**Why is there no alternative today?** Pure visibility gap — the register is
writable and meaningful, but not exposed. Frost protection is currently a
touch-panel-only setting.

---

### P2 — `binary_sensor.vallox_in_bypass`

| | |
|---|---|
| Metric key | `A_CYC_IN_BYPASS` |
| Address | 5126 |
| Default | `off` (raw 0) |
| Writable | No — status flag, read-only |

**What it does.** `on` while the bypass damper is actually open (free-cooling /
free-heating path active), regardless of why. This is a more direct signal than
deriving it from `sensor.cell_state` (which also reports `COOLRECO`, `DEFROST`,
etc.).

**When is it useful?** As a trigger/condition for cooling automations ("only
raise fan speed once the unit is actually bypassing") and as a dashboard
confirmation that the P0 lever worked. No behaviour change from setting it; it's
read-only.

**Why no alternative today?** `sensor.cell_state` exists but requires the user
to string-match "Bypass". A dedicated binary sensor is cheaper to use in
templates and automations.

---

### P2 — `binary_sensor.vallox_dewpoint_limit_in_use`

| | |
|---|---|
| Metric key | `A_CYC_DEWPOINT_LIMIT_IN_USE` |
| Address | 20555 |
| Default | `on` (raw 1) |
| Writable | **No** — the investigation found this is touch-panel-only, not websocket-settable. Expose read-only only. |

**What it does.** `on` when the unit's dewpoint-based condensation-prevention
limit is governing the supply temperature (it prevents supply-duct sweating
when delivering cold air through warm, humid duct spaces).

**When is it useful?** Pure diagnostics — explains *why* a bypass or a low
supply target isn't producing as cold a supply as expected (the dewpoint limit
is tempering it to avoid condensation). Read-only; do **not** expose as a
switch — writing it is not supported by the firmware.

**Why no alternative today?** Not exposed at all; users have no way to see
whether the dewpoint limit is active.

---

### Optional — two flags with uncertain semantics (probe before exposing)

These are present in the data model but the investigation only notes their
semantics are "only partly documented". List for a maintainer to decide after a
writability + effect probe; do **not** ship as settable without that.

| Entity candidate | Metric key | Address | Current raw | Note |
|---|---|---|---|---|
| `switch.vallox_coolrecovery_disabled` | `A_CYC_COOLRECOVERY_DISABLED` | 20516 | 0 (= cool recovery **enabled**) | `on` would *disable* cool recovery — naming is inverted vs. the integration's existing `bypass_locked`; consider exposing as `binary_sensor` (read-only) until effect is verified |
| `switch.vallox_summer_time_auto` | `A_CYC_SUMMER_TIME_AUTO_ENAB` | 21768 | 1 (= auto enabled) | appears to gate automatic summer-mode switching; effect unverified |

## 4. Implementation notes

- **Pattern is generic.** `number.py` already defines `ValloxNumberEntityDescription`
  with a `metric_key` and `async_set_native_value` calls
  `client.set_values({metric_key: value})`. The Celsius→centi-Kelvin conversion is
  handled inside `vallox_websocket_api` for known temperature metrics — proven by
  the existing temp-target entities *and* by this repo's `h7_start.py`
  (writes `5.0`, raw readback verifies `5.00 °C`). So P0 and the defrost number
  are each **one entry** in `NUMBER_ENTITIES` plus one `strings.json` string. No
  other code.
- **New `select.py` platform.** The integration has no select platform today.
  Add a thin `ValloxSelectEntityDescription(metric_key, options: list[str],
  value_to_option: dict[int,str], option_to_value: dict[str,int])` and a
  `ValloxSelectEntity` whose `async_set_native_value` calls
  `client.set_values({metric_key: option_to_value[value]})`. Register it in
  `__init__.py`'s `async_setup_entry` platforms tuple. This unlocks any future
  enum register (e.g. `A_CYC_RH_LEVEL_MODE`, `A_CYC_OPT_TEMP_SENSOR_MODE`).
- **New `binary_sensor.py` entries.** The integration already has a binary_sensor
  platform (it exposes `post_heater` from `A_CYC_IO_HEATER`). Add
  `ValloxBinarySensorEntityDescription` entries for `A_CYC_IN_BYPASS` and
  `A_CYC_DEWPOINT_LIMIT_IN_USE` with `is_on ⇔ value == 1`, `entity_category=config`
  (or `diagnostic` for the dewpoint one).
- **Translations.** Add a `name` (and optionally a `description` under
  `entity.components.vallox.*` if the integration uses docs descriptions) for
  each new key in `strings.json` and at least `translations/en.json`. The names
  above are deliberately disambiguated: "Heating season setpoint" (not just
  "Winter setpoint") because a *different* register `A_CYC_MLV_WINTER_SETPOINT`
  (address 20531, currently 2.0 °C) is the MLV-module minimum-supply winter
  setpoint — exposing both later under bare "winter setpoint" would collide.
- **Verification.** HA's Vallox integration polls via the websocket table read
  on a 60 s interval. `fetch_metrics` returns 0 for centi-Kelvin registers on
  this firmware (a known issue documented in `../vallox-logger/vallox_raw.py`), but
  the integration's own coordinator reads the raw table the same way the
  existing temp-target entities do, so the value displayed for P0/P1-number will
  be correct. Confirm on hardware that the `native_value` shown matches a raw
  readback after a write.
- **Ranges to confirm on hardware before merging:**
  - `A_CYC_POST_HEATER_WINTER_SETPOINT`: min proven 5.0; confirm max (proposed 25).
  - `A_CYC_SUPPLY_AIR_DEFROST_TEMP`: min confirmed 10 (firmware clamps); confirm
    max (proposed 20). Document the clamp in the entity description.
  - `A_CYC_SUPPLY_HEATING_ADJUST_MODE`: confirm all three options are accepted
    and the readback is exact (the repo's probes wrote `2` and read it back, but
    `1` was not exhaustively verified).

## 5. Explicitly rejected (do not add)

| Register | Why rejected |
|---|---|
| `A_CYC_BYPASS_LOCKED` | Already exposed as `switch.bypass_locked`. Its name is misleading (ON = force heat recovery / block bypass), but that is a docs problem, not a new-entity problem. The investigation confirmed it can only block bypass, never compel it — it is not a cooling lever. |
| `A_CYC_PARTIAL_BYPASS` / `A_CYC_PARTIAL_BYPASS_DISABLED` | Tested inert on this model (`../vallox-logger/FINDINGS.md`): cycled 0/1/2 with no observable effect on cell state, bypass I/O, or supply temp. Likely a vestige for a model with a modulating damper. Don't expose. |
| `A_CYC_MLV_SUPPLY_LOWER_LIMIT` | Falsified as a live clamp: a live write of 10 °C was accepted but delivered supply glided straight through 18 °C with no clamping reaction. Does nothing observable on this firmware; would mislead users. |
| `A_CYC_DEWPOINT_LIMIT_IN_USE` *as a switch* | Not websocket-settable on this firmware (touch-panel only). Expose read-only only (P2 above). |
| `A_CYC_MLV_WINTER_SETPOINT` | Distinct register (post-heater vs MLV minimum-supply). Not part of this cooling solution; out of scope for this spec. If added later, name it "MLV winter setpoint" to avoid collision with P0. |

## 6. Open questions for the maintainer

1. Is the maintainers willing to take the P0 entity upstream, given its
   automation-safety implications? If yes, the PR should carry a docs note that
   a low value must be reverted before the heating season.
2. Should the select platform land together with P0, or as a follow-up? P0 alone
   unblocks the cooling automation; the select is a nice-to-have that adds a
   whole new platform.
3. Confirm the upper bounds for the two temperature numbers on a unit with the
   post-heater fitted (this repo's unit has one; values above 25 °C were never
   tested).
4. Decide on `entity_category`: `config` for all settable ones (consistent with
   the existing `number` entities, which set `_attr_entity_category = CONFIG`),
   `diagnostic` for the two read-only binary sensors.

## 7. References (in the sister repo `../vallox-logger/`)

- `../vallox-logger/INVESTIGATION.md` — falsified-lever table, H7 verification, campaign log.
- `../vallox-logger/REPORT_FINAL_SOLUTION.md` — the three-lever solution and the 5 °C / 8 °C / 60 %
  values.
- `../vallox-logger/FINDINGS.md` — `BYPASS_LOCKED` one-direction behaviour, `PARTIAL_BYPASS`
  inertness, `MLV_SUPPLY_LOWER_LIMIT` non-clamping.
- `../vallox-logger/schema_constants.json` / `../vallox-logger/schema_raw_dump.json` — addresses, enums, current
  raw values.
- `../vallox-logger/archive/experiments/{h7_start,stack_start,cooling_mode_start,test_heating_adjust_mode,test_heating_season_writable}.py`
  — the write/verify scripts proving writability of each P0/P1 register.
- `HA_AUTOMATION_PLAN.md` — the HA automation that consumes the P0 entity.