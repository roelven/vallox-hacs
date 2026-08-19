# Roadmap — extended Vallox HACS integration

Built TDD: for each step we first add/extend a failing test, implement until the
test passes, then commit. Tests run under `pytest` against a released Home
Assistant (currently 2026.2.x) in `.venv/`.

The goal (from `HANDOFF.md` + `HA_INTEGRATION_SPEC.md`): turn the scaffolded
fork into a working HACS integration that exposes the heating-season / cooling
registers and the two nocturnal-cooling services, with raw-readback
verification.

## Step 0 — Environment & repo hygiene

- Create `.venv` (Python 3.13) with `homeassistant`, `vallox-websocket-api`,
  `pytest`, `pytest-asyncio`, `ruff`.
- Add `requirements_test.txt` so the env is reproducible.
- Add a `[tool.ruff]` block to `pyproject.toml` matching HA core defaults.
- Commit.

## Step 1 — Make the vendored modules import on a released HA

The scaffold was generated from HA core `dev`, which is ahead of the latest
release: it uses `AddConfigEntryEntitiesCallback` (fine on ≥2025.2), forward-ref
entity annotations that need `from __future__ import annotations`, and the
not-yet-released `UnitOfRatio` enum. Fix those so every module imports on a
released HA.

- Test: `test_module_imports.py` imports every `custom_components.vallox`
  module and asserts `async_setup_entry`/platform setup callables exist.
- Fix: `from __future__ import annotations` in number/binary_sensor/sensor/
  switch; `UnitOfRatio.PERCENTAGE`→`PERCENTAGE`,
  `UnitOfRatio.PARTS_PER_MILLION`→`CONCENTRATION_PARTS_PER_MILLION` in
  sensor.py.
- Commit.

## Step 2 — const.py: new constants

- Test: `test_const.py` asserts the adjust-mode enum maps, the service names,
  and the cooling/commissioned setpoint constants.
- Implement in `const.py`.
- Commit.

## Step 3 — number.py: heating_season_setpoint + supply_air_defrost_temp

- Test: `test_entity_descriptions.py` number cases (already drafted) pass.
- Append the two `ValloxNumberEntityDescription`s.
- Commit.

## Step 4 — select.py: new select platform + register in __init__.py

- Test: `test_entity_descriptions.py` select case passes; `Platform.SELECT` in
  `__init__.PLATFORMS`.
- Implement `select.py` (generic `ValloxSelectEntityDescription` with
  `options_map`/`reverse_map`) and add `Platform.SELECT` to `PLATFORMS`.
- Commit.

## Step 5 — binary_sensor.py: in_bypass + dewpoint_limit_in_use

- Test: `test_entity_descriptions.py` binary_sensor cases assert the two new
  descriptions and their metric keys / entity categories.
- Append the two descriptions.
- Commit.

## Step 6 — readback.py: centi-Kelvin conversion + raw table read

- Test: `test_readback_conversion.py` imports the real `to_c` from
  `readback.py` and round-trips known points + sentinels.
- Implement `readback.py` (`to_c`, `read_raw`) ported from
  `../vallox-logger/vallox_raw.py`.
- Commit.

## Step 7 — services.py: start/stop_nocturnal_cooling

- Snapshot the current profile on the coordinator
  (`nocturnal_cooling_prev_profile`), never on a user-facing helper.
- start: write H7=5 + Away target=8, verify by raw readback, set_profile(AWAY).
- stop: write H7=15 + Away target=20, verify, restore snapshotted profile,
  clear the snapshot. No-op if no snapshot.
- On readback mismatch raise `HomeAssistantError` with
  `nocturnal_cooling_verify_failed`.
- Test: `test_services.py` real cases (start writes+verifies, stop reverts,
  stop-without-start no-op, mismatch raises) against a `FakeVallox` +
  fake coordinator, monkeypatching `read_raw`.
- Register both services in `async_setup_services`.
- Commit.

## Step 8 — services.yaml + coordinator snapshot attribute

- Add `start_nocturnal_cooling` / `stop_nocturnal_cooling` schemas (no fields).
- Add `nocturnal_cooling_prev_profile: Profile | None = None` default on the
  coordinator class.
- Test: `test_services_yaml.py` parses services.yaml and asserts the two keys;
  `test_const`/coordinator test asserts the snapshot attr default.
- Commit.

## Step 9 — manifest / hacs metadata polish

- Bump `manifest.json` version, keep `iot_class=local_polling`, keep
  `requirements` pinned.
- Confirm `hacs.json` minimum HA matches what we actually test against.
- Test: `test_manifest.py` asserts required manifest keys and that
  `requirements` pins `vallox-websocket-api`.
- Commit.

## Step 10 — Full suite + ruff green

- `ruff check . --fix` + `ruff format .` clean.
- `pytest -q` all green.
- Commit.