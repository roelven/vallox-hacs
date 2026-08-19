# Plan: Nocturnal cooling via a HACS Vallox integration fork

**Status:** re-articulated 2026-08-18. The HACS fork is now the primary path. The
sidecar and the one-line custom-component-shadow options are demoted to
alternatives. The companion spec `HA_INTEGRATION_SPEC.md` defines *what* the
fork adds; this file defines *how* we build, test, migrate, and run it.

## 1. Decision

Build a **HACS custom integration** that is a fork of the official
`homeassistant/components/vallox/`, extended with the registers in
`HA_INTEGRATION_SPEC.md`, and with a first-class `vallox.start_nocturnal_cooling`
/ `vallox.stop_nocturnal_cooling` service that does the verified write+revert.

- **Same domain (`vallox`)**, so the existing config entry and entity IDs survive.
- **No second VM.** Testing is unit tests + standalone write-verification against
  the real unit (already proven by this repo's scripts) + installing on the live
  HA at `192.168.20.7:8123`, which has a solid backup strategy.
- **Cooling logic lives in the component as a verified service**, not as
  fire-and-forget YAML.
- **Core PR comes later**, once the fork is proven in production. The fork's diff
  stays "upstream + our additions" so it can collapse back when the PR merges.

## 2. Production HA — current state (verified 2026-08-18)

The built-in Vallox integration is loaded and exposes **25 entities**. The ones
in active use for comfort/CO2 are:

| Entity | State | Role |
|---|---|---|
| `sensor.vallox_carbon_dioxide` | 586 | **CO2 — keep** |
| `sensor.vallox_outdoor_air` / `_extract_air` / `_exhaust_air` / `_supply_air` / `_supply_cell_air` | temps | **temperatures — keep** |
| `sensor.vallox_humidity` | 65 | RH — keep |
| `sensor.vallox_fan_speed` / `_cell_state` / `_current_profile` | status | keep |
| `number.vallox_supply_air_temperature_{home,away,boost}` | 20/20/18 | per-profile supply target |
| `fan.vallox` | on | profile + speed |
| `switch.vallox_bypass_locked` | off | (misleading name; see §6) |
| `binary_sensor.vallox_post_heater`, `date.vallox_filter_change_date`, `sensor.vallox_remaining_time_for_filter`, `sensor.vallox_profile_duration` | — | keep |

**Entity-id rule (corrected from earlier drafts):** HA derives the slug from the
friendly name, not the translation key. So the existing target entities are
`number.vallox_supply_air_temperature_*` (the name "Supply air temperature
(Home)"), *not* `…_target_*`. Our new entities will therefore be:

- `number.vallox_heating_season_setpoint` (P0, the H7 lever)
- `number.vallox_supply_air_defrost_temp` (P1)
- `select.vallox_supply_heating_adjust_mode` (P1, new select platform)
- `binary_sensor.vallox_in_bypass` (P2)
- `binary_sensor.vallox_dewpoint_limit_in_use` (P2)

**Existing profile-switch automations** (5 KNX↔Vallox automations; 4 unavailable,
1 disabled by the user) write to `input_text.vallox_previous_profile`
(currently "away") to snapshot/restore the profile when certain KNX lights turn
on/off. Our cooling service must use a **separate snapshot** to avoid clobbering
this KNX flow.

## 3. The fork — what it adds vs preserves

```
vallox-hacs/                                  # HACS custom repo (type: integration)
├── hacs.json
├── LICENSE                                   # MIT, "derived from home-assistant/core" notice
├── README.md
├── custom_components/vallox/
│   ├── manifest.json                         # domain: vallox; requirements: ["vallox_websocket_api==<pinned>"]; version; issue_tracker
│   ├── __init__.py                            # + register select platform + the two services
│   ├── const.py                              # + service names, ADJUST_MODE enum maps
│   ├── coordinator.py / config_flow.py / entity.py   # unchanged (keeps the existing entry valid)
│   ├── number.py                             # + heating_season_setpoint, supply_air_defrost_temp
│   ├── select.py                             # NEW: supply_heating_adjust_mode (Supply/Extract/Cooling)
│   ├── binary_sensor.py                      # + in_bypass, dewpoint_limit_in_use
│   ├── fan.py / sensor.py / switch.py / date.py      # unchanged
│   ├── services.py                           # NEW: start/stop_nocturnal_cooling (write + raw readback + profile snapshot)
│   ├── services.yaml
│   ├── strings.json / translations/en.json   # + new entity + service strings
│   └── blueprints/...  (or top-level blueprints/)
├── blueprints/automation/vallox_nocturnal_cooling.yaml
└── tests/
    ├── test_entity_descriptions.py
    ├── test_readback_conversion.py
    └── test_services.py
```

**Preserved unchanged** (so the CO2/temperature/humidity sensors and the existing
entities keep their entity_ids): `sensor.py`, `fan.py`, `switch.py`,
`binary_sensor.py`'s existing `post_heater`, `date.py`, `coordinator.py`,
`config_flow.py`, `entity.py`.

**Added**, per `HA_INTEGRATION_SPEC.md`:
- `number.vallox_heating_season_setpoint` ← `A_CYC_POST_HEATER_WINTER_SETPOINT`
  (the decisive H7 lever).
- `number.vallox_supply_air_defrost_temp` ← `A_CYC_SUPPLY_AIR_DEFROST_TEMP`
  (frost protection; description warns it is *not* a cooling lever).
- `select.vallox_supply_heating_adjust_mode` ← `A_CYC_SUPPLY_HEATING_ADJUST_MODE`
  (Supply/Extract/Cooling), via a new generic `select.py` platform.
- `binary_sensor.vallox_in_bypass` ← `A_CYC_IN_BYPASS`.
- `binary_sensor.vallox_dewpoint_limit_in_use` ← `A_CYC_DEWPOINT_LIMIT_IN_USE`
  (read-only; not websocket-settable).

**New services** (the heart of the cooling routine):

- `vallox.start_nocturnal_cooling` — snapshots the current profile into the
  component's runtime state (a dedicated slot, *not* `input_text.vallox_previous_profile`),
  writes `A_CYC_POST_HEATER_WINTER_SETPOINT=5`, `A_CYC_AWAY_AIR_TEMP_TARGET=8`,
  switches the unit to the **Away** profile (whose fan speed the household has
  pre-tuned on the panel — the comfort dial), then **raw-reads-back every write**
  and raises `HomeAssistantError` on mismatch. This is `h7_start.py` +
  `stack_start.py` ported into the component, with the "raw log is the only
  proof" rule enforced inside the integration.
- `vallox.stop_nocturnal_cooling` — restores the snapshotted profile, writes
  `A_CYC_POST_HEATER_WINTER_SETPOINT=15`, `A_CYC_AWAY_AIR_TEMP_TARGET=20`,
  readback-verifies. Idempotent: if no cooling is active, it's a no-op (or a
  commissioned-baseline restore).

Why a service beats YAML `number.set_value` calls: the write + the readback
verification + the profile snapshot are atomic and owned by the component, so
the "verify every write by raw readback" methodology that this whole
investigation depended on becomes a property of the integration rather than a
promise in an automation script.

## 4. Migration (no entity loss)

The existing config entry must **stay** so entity unique IDs
(`{device_uuid}-{key}`) and entity_ids carry over. The custom component shadows
the built-in on restart.

1. Back up HA (you have a solid strategy).
2. Install the fork via HACS (custom repo). This drops
   `custom_components/vallox/` over the built-in.
3. **Restart HA.** HA now loads `custom_components/vallox` for the `vallox`
   domain. The existing config entry re-initialises against the fork; the
   existing entities (CO2, temperatures, fan, targets, bypass_locked) keep their
   entity_ids; the five new entities appear.
4. Verify in Developer Tools → States that
   `sensor.vallox_carbon_dioxide`, `sensor.vallox_outdoor_air`,
   `sensor.vallox_extract_air`, etc. are present and reporting, and that the
   new `number.vallox_heating_season_setpoint` shows `15.0`.

**Do not** delete the config entry or "disable" it before installing — that
would unload the entities and risk `_2` suffixes on re-add. Just install over it
and restart. If you already disabled the entry, re-enable it after install.

The `switch.vallox_bypass_locked` entity continues to exist (from `switch.py`,
unchanged). Leave it OFF.

## 5. Testing without a second VM

- **Unit tests** (`tests/`): pure logic — entity descriptions, the select's
  option↔int maps, the centi-Kelvin↔Celsius readback conversion, and the service's
  write/verify path against a mocked client. Run with `pytest` anywhere (this VM
  is fine).
- **Standalone write-verification** before wrapping in the component: the repo
  already proves every P0/P1 register is websocket-writable with exact
  readback (`h7_start.py`, `stack_start.py`, `cooling_mode_start.py`,
  `test_heating_season_writable.py`). The component's service reuses this exact
  read path, so the write logic is already validated against the real unit.
- **Install on the live HA**, then observe:
  - HA history (the new entities report and accept writes).
  - The existing `collector.py` logger (in `../vallox-logger/`, still on this VM while it lives) captures
    the raw register table every 60 s — the same evidence trail used for the
    whole investigation. Run the first cooling night with the logger running and
    confirm in `~/vallox-logs/*.jsonl` that `A_CYC_POST_HEATER_WINTER_SETPOINT`
    read back 5.0, the profile flipped to Away, and `A_CYC_CELL_STATE` went to
    BYPASS below 15.7 °C.
- **Backups** carry the production risk: if a build misbehaves, restore HA and
  remove the custom component. The unit itself is never at risk because every
  write is reversible and the commissioned baseline is in
  `../vallox-logger/commissioning/settings-20260813-VKioD.percent_conf` + `../vallox-logger/restore_commissioned.py`.

> Note on the logger: `../vallox-logger/collector.py` runs on this non-persistent VM. It is not
> required for the automation, only for the evidence trail during test nights.
> If the VM is down on a test night, fall back to HA history + the component's
> own readback-verification logs. Long-term logging continuity is a separate
> decision (alternative A7).

## 6. The cooling automation (after the fork is installed)

A blueprint ships in the repo; importing it creates the three automations. The
shape from the prior plan holds, but actions are now one service call each:

- **START** — trigger: `time 22:00` *or* `numeric_state` outdoor crossing below
  extract during 22:00–05:00. Conditions: armed, in-window, `outdoor ≤ extract`,
  `outdoor ≥ 10`, season guard (Apr–Sep, tune), not already active. Action:
  `service: vallox.start_nocturnal_cooling`.
- **REVERT (primary)** — `time 05:00` → `service: vallox.stop_nocturnal_cooling`.
- **REVERT (backup)** — `time 05:05` → `service: vallox.stop_nocturnal_cooling`
  (idempotent).
- **REVERT on HA start** — `homeassistant start` →
  `service: vallox.stop_nocturnal_cooling` (the critical safety net; the service
  is a no-op if cooling isn't active, so it's safe to fire unconditionally).

The service holds the "previous profile" snapshot internally (config-entry
runtime state), so it does **not** touch `input_text.vallox_previous_profile` and
won't fight the KNX light→Away automations. If a KNX Away-trigger fires during
the cooling window, the unit is already Away; when the KNX restore fires it
would switch back to the KNX-snapshotted profile — flag this as an interaction
to verify, but note that 4 of the 5 KNX automations are currently `unavailable`
and the 5th is disabled, so the risk is low in practice.

**`switch.vallox_bypass_locked`** stays OFF and untouched. Recap of the
finding: ON force-locks the unit into heat recovery (blocks bypass); OFF is a
no-op on a cold night because the automatic logic already chooses HEATRECO. It
is not a cooling lever — our H7 setpoint changes what the automatic logic
*wants* to do. See `HA_INTEGRATION_SPEC.md` §5 and `../vallox-logger/FINDINGS.md`.

## 7. Alternatives (demoted)

- **A-fork (this plan).** Primary.
- **B — Upstream PR only.** Clean end-state; deferred until the fork is proven.
  The user owns this step.
- **C — One-line custom component shadow (no services, no select).** The
  earlier primary; strictly less capable than A (no verified-write service, no
  blueprint). Kept as the "minimal" fallback if A turns out to be more
  maintenance than wanted.
- **D — Sidecar HTTP service.** Subsumed by A. Not worth reintroducing.
- **E — Pure official integration (no H7).** Cannot cool on a 9–15 °C night;
  rejected by the data.
- **F — Relocate the Python+systemd stack to a persistent host.** The
  "do nothing in HA" fallback; only relevant if HACS proves unworkable.
- **G — `shell_command` to a Python script on the HA host.** Only viable on HA
  Container/Supervised, not HA OS; moot under A.

## 8. Prerequisites / open items

1. **Public or private HACS repo?** Affects README/licensing tone. Decide before
   scaffolding. Private (install-from-Git-URL) is fine and avoids store-quality
   pressure.
2. **Pin `vallox_websocket_api` version** in `manifest.json` to the one already
   proven on this firmware (the version in this repo's `.venv`).
3. **Confirm ranges on hardware** before release:
   `A_CYC_POST_HEATER_WINTER_SETPOINT` min proven 5.0 (confirm max, propose 25);
   `A_CYC_SUPPLY_AIR_DEFROST_TEMP` min confirmed 10 (firmware clamp; confirm max,
   propose 20); `A_CYC_SUPPLY_HEATING_ADJUST_MODE` all three options accepted.
4. **Verify the KNX↔Vallox automations** are disabled/unavailable (they appear
   to be) so they won't fight the cooling service's profile snapshot. If any are
   re-enabled later, coordinate the two snapshot slots.
5. **Logger continuity**: decide whether `../vallox-logger/collector.py` should relocate so the
   test-night evidence trail is available long-term. Independent of this plan.
6. **Season window**: the Apr–Sep guard is a placeholder; tune from
   PirateWeather / historical outdoor data.

## 9. What does NOT change

- The unit, the websocket API, the centi-Kelvin encoding, the KNX boosts, and the
  "raw log is the only proof" rule.
- The four cooling values (H7=5, AWAY target=8, Away profile fan speed
  user-tuned, profile=Away) and the four commissioned revert values (H7=15,
  AWAY target=20, profile=snapshotted, fan speed untouched).
- `../vallox-logger/vallox_raw.py`'s readback approach is reused inside the component's service.
- `HA_INTEGRATION_SPEC.md` remains the authoritative list of *what* the fork
  adds; this file is the *how*.