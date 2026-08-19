# Vallox (extended) — HACS integration

A fork of the Home Assistant [Vallox integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/vallox)
that adds the seasonal/frost/mode registers needed for **nocturnal summer cooling**
and ships a verified `start_nocturnal_cooling` / `stop_nocturnal_cooling` service.

It uses the **same `vallox` domain** as the built-in integration, so installing
it over the built-in preserves your existing config entry and entity IDs
(`sensor.vallox_carbon_dioxide`, the temperature sensors, `fan.vallox`, the
per-profile supply-air targets, `switch.vallox_bypass_locked`, etc.) and just
adds the new ones on top.

## What this adds

| New entity | Register | Why |
|---|---|---|
| `number.vallox_heating_season_setpoint` | `A_CYC_POST_HEATER_WINTER_SETPOINT` | The decisive lever: the outdoor temperature below which the unit switches to winter heat-recovery. Lower it (e.g. to 5 °C) for the night to keep the bypass open on a 9–15 °C summer night. **Must revert before the heating season.** |
| `number.vallox_supply_air_defrost_temp` | `A_CYC_SUPPLY_AIR_DEFROST_TEMP` | Frost-protection threshold (winter). Not a cooling control — verified. |
| `select.vallox_supply_heating_adjust_mode` | `A_CYC_SUPPLY_HEATING_ADJUST_MODE` | Supply / Extract / Cooling control mode (the manufacturer's summer-cooling switch). |
| `binary_sensor.vallox_in_bypass` | `A_CYC_IN_BYPASS` | Bypass damper actually open (read-only). |
| `binary_sensor.vallox_dewpoint_limit_in_use` | `A_CYC_DEWPOINT_LIMIT_IN_USE` | Dewpoint condensation-prevention active (read-only; not websocket-settable). |

| New service | What it does |
|---|---|
| `vallox.start_nocturnal_cooling` | Snapshots the current profile, writes H7 setpoint=5 + Away target=8, switches to the Away profile (whose fan speed you pre-tune as the cooling intensity), and **verifies every write by raw register readback**. |
| `vallox.stop_nocturnal_cooling` | Reverts H7 setpoint=15, Away target=20, restores the snapshotted profile. Idempotent. |

The full register-level rationale (which levers work, which were falsified, the
safety constraints) is in the sister repository:
[`HA_INTEGRATION_SPEC.md`](HA_INTEGRATION_SPEC.md)
and [`HA_AUTOMATION_PLAN.md`](HA_AUTOMATION_PLAN.md).

## Install (over the built-in)

1. Add this repository to HACS as a custom integration (type: Integration).
2. Install "Vallox (extended)", then restart Home Assistant.
3. Your existing Vallox config entry re-initialises against this fork; the
   existing entities keep their IDs and the new ones appear.

**Do not delete your existing Vallox config entry** — keeping it is what
preserves the entity IDs. Just install over it and restart.

## Blueprints

After install, import the two blueprints from `blueprints/automation/`:
- `vallox_nocturnal_cooling.yaml` — engages cooling between a start and end
  time once outdoor falls below extract.
- `vallox_nocturnal_cooling_revert.yaml` — the three-layer revert (end time,
  backup +5 min, on Home Assistant start).

## Status

Work in progress. See `HANDOFF.md` for the build task list and the exact code
changes still to land. The intent is that the minimal, high-value subset
(`number.vallox_heating_season_setpoint` + the two cooling services) gets
submitted upstream to `home-assistant/core` once it's proven in production; this
fork then collapses back toward upstream.

## License

MIT, derived from `home-assistant/core`'s Vallox integration. See `LICENSE`.