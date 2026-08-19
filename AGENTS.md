# AGENTS.md — Home Assistant Custom Integration / HACS Plugin

Instructions for AI coding agents (Claude, Copilot, Cursor, Codex, etc.) working in
this repository. This project is a **Home Assistant custom integration** distributed
outside HA Core, typically via **HACS**. Follow these rules over your own defaults.
Read this whole file before writing code. If a nested `AGENTS.md` exists closer to
the file you're editing (e.g. inside `custom_components/<domain>/`), that one takes
precedence for that subtree.

---

## 1. Orient yourself first

Three things are easy to conflate — check which one you're actually in before acting:

- **Home Assistant Core** (`home-assistant/core`) — the built-in `homeassistant/components/`
  tree. Different rules, different PR process, different `AGENTS.md`. Do not assume
  core conventions apply here without checking; some do, some (like `requirements_all.txt`,
  core's `CODEOWNERS` mechanics, or core's release train) do not.
- **Custom integration** (this repo, most likely) — lives under `custom_components/<domain>/`,
  installed by users via HACS or manual copy. This file's home turf.
- **HACS itself** — the distribution/discovery layer (an integration + frontend panel).
  You are not building HACS; you are building something HACS *distributes*. Category
  matters: `integration`, `plugin` (Lovelace/frontend card), `theme`, `python_script`,
  `appdaemon`, `template`. Most of this document targets **integrations**; if this repo
  is a frontend plugin or theme instead, skip the entity/config-flow/coordinator sections
  and keep the HACS packaging, versioning, and repo-hygiene sections.

## 2. AI contribution & disclosure policy — read before opening any PR

The Open Home Foundation (which governs the `home-assistant` and `home-assistant-libs`
GitHub orgs) has a published AI policy: AI tools are welcome as an aid, but **autonomous
agents may not submit PRs or issues unsupervised**, and the human contributor must be
able to explain and defend every change without AI assistance. That policy formally
applies to contributions *into HA Core / official org repos*, not to a third-party
HACS repo you maintain yourself — but treat it as the ecosystem's cultural norm here too:

- **Never commit or open a PR autonomously.** Prepare the change, explain it, and wait
  for explicit human approval before committing — even if you were asked to "fix" or
  "implement" something end-to-end.
- **Disclose AI involvement** in commit messages / PR descriptions when you are the
  author of record, unless the maintainer has said this isn't necessary for this repo.
- **Never fabricate changelogs, device compatibility claims, or test results.** If you
  didn't run it against real hardware, say so.
- If this repo has its own `AI_POLICY.md` or `CONTRIBUTING.md`, that supersedes this
  section.

## 3. Required repository layout (HACS integration)

```
repo-root/
├── custom_components/
│   └── <domain>/                  # exactly ONE integration per repo
│       ├── __init__.py            # async_setup_entry / async_unload_entry
│       ├── manifest.json          # required, see §4
│       ├── config_flow.py         # UI setup is mandatory for new integrations
│       ├── const.py
│       ├── coordinator.py         # DataUpdateCoordinator, if polling
│       ├── diagnostics.py         # recommended (Gold requirement)
│       ├── strings.json           # source of truth for all user-facing text
│       ├── translations/
│       │   └── en.json            # generated from strings.json, do not hand-edit both
│       ├── <platform>.py          # sensor.py, switch.py, etc.
│       └── services.yaml          # if the integration registers service actions
├── tests/
│   └── components/<domain>/
├── .github/workflows/             # hassfest + hacs validation + CI
├── hacs.json                      # HACS manifest, see §9
├── README.md                      # required by HACS, must include install + usage
└── info.md                        # optional, shown in HACS UI if present
```

Rules that trip people up:

- Only one subdirectory under `custom_components/` per repo, unless `content_in_root`
  is explicitly set in `hacs.json`.
- All device/service communication goes through a **separate PyPI-published async
  Python library**, not inline `requests`/`aiohttp` calls in the integration. HA does
  not want protocol code living in the integration itself. If no such library exists
  yet, that library is a separate project/package with its own repo, its own issue
  tracker, source distribution, and OSI license — reference it from `manifest.json`'s
  `requirements`.
- Don't invent files "for consistency with core" that HACS/custom components don't
  need (e.g. `requirements_all.txt` — that's core-only).

## 4. `manifest.json` — required keys

```json
{
  "domain": "your_domain",
  "name": "Your Integration",
  "codeowners": ["@your-github-handle"],
  "config_flow": true,
  "documentation": "https://github.com/you/repo",
  "issue_tracker": "https://github.com/you/repo/issues",
  "iot_class": "cloud_polling",
  "requirements": ["your-lib==1.2.3"],
  "version": "1.2.3"
}
```

- `version` is **mandatory for custom components** (core integrations omit it; this
  repo is not core, so include it and bump it every release).
- `iot_class` must accurately reflect reality (`local_push`, `local_polling`,
  `cloud_push`, `cloud_polling`, `assumed_state`, `calculated`) — agents should not
  default to `cloud_polling` without checking how the device actually communicates.
- Run `python3 -m script.hassfest` (or the repo's pinned equivalent, often exposed via
  a `script/` wrapper or pre-commit hook) before committing manifest/translation
  changes — it validates manifest schema, codeowners, and translations consistency.
  Don't hand-verify what a validator already checks.

## 5. Environment & commands

Prefer whatever wrapper scripts this repo ships (`script/setup`, `scripts/develop`,
`Makefile`, devcontainer tasks) over ad hoc invocations — they pin versions and flags
that matter. If none exist, these are the ecosystem defaults:

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt   # or requirements_dev.txt
pip install -e .

# Lint / format (Ruff is standard across the ecosystem)
ruff check . --fix
ruff format .

# Typing (pyright or mypy, whichever this repo is configured for — check pyproject.toml)
mypy custom_components/<domain>
# or: pyright custom_components/<domain>

# Tests (needs the pytest-homeassistant-custom-component fixture package for
# custom-component repos, since this isn't HA Core's own test tree)
pip install pytest-homeassistant-custom-component
pytest tests/ -q
pytest tests/components/<domain>/ --cov=custom_components.<domain> --cov-report term-missing

# Manifest / translations / codeowners validation
python3 -m script.hassfest

# Run a real HA instance against this integration
hass -c config/ --skip-pip
```

Never invent your own bespoke `pip`/`pytest`/`ruff` invocation when a project script
exists for it — use the project's script so flags and plugin config stay consistent
with CI.

## 6. Non-negotiable architecture rules

These are the rules that get PRs rejected or integrations pulled from HACS if broken:

- **Config flow only.** New integrations must be settable up entirely through the UI.
  `configuration.yaml`-based setup is deprecated; don't add YAML schema config for a
  new integration.
- **Stable `unique_id`.** Must be a device serial number, MAC address, or account ID —
  never an IP address, hostname, or anything the user can change. Set it once, in the
  config flow, before creating the entry.
- **One config entry per physical device/account.** Guard against duplicates with
  `self._abort_if_unique_id_configured()` / `unique-config-entry`.
- **Layering**: entity → coordinator → external library. Entities never talk to the
  network directly; coordinators own polling/push and fan data out to entities.
- **`has_entity_name = True`** on all new entities. The entity's own `name` describes
  only the data point ("Battery", "Power usage"), never the device or integration
  name — HA composes `device.name + entity.name` for you. The primary/main entity of
  a device may return `None` for `name`.
- **`device_info`** set on every entity so devices register correctly and group their
  entities.
- **`ConfigEntry.runtime_data`** for runtime state — don't stash it in `hass.data[DOMAIN]`
  dicts for new code.
- **Async all the way.** No blocking I/O in the event loop; no bare `requests` calls;
  wrap sync libraries with `hass.async_add_executor_job`.
- **Reauth flow** for anything credential-based — expired/revoked auth must prompt an
  in-UI reauth, not silently fail or force a delete-and-re-add.
- **Raise on failure, don't swallow.** Service actions raise `HomeAssistantError` /
  `ServiceValidationError` on failure, with a translatable message — never return
  `None` or log-and-continue on a real error.

## 7. Coding standards

- PEP 8 + PEP 257, enforced by Ruff — don't hand-format around what Ruff would flag.
- Full type hints on all new code, including test functions. Prefer concrete types
  (`HomeAssistant`, `ConfigEntry`, `MockConfigEntry`) over `Any`.
- f-strings for normal string building. For `_LOGGER` calls specifically, use `%s`
  lazy formatting (`_LOGGER.error("No route to device: %s", host)`), not f-strings —
  avoids formatting cost when the log level is disabled.
- No periods at the end of log messages. No secrets, tokens, passwords, or full
  auth headers in any log line, ever, at any level.
- Docstrings: one-line summary as a full sentence with a period; Google-style for
  anything longer. Type info goes in annotations, not in the docstring text.
- Comments explain *why*, never *what*. Don't add a comment that just restates the
  line below it (`# check initialized` above `if self.initialized:`). Comment on
  workarounds, non-obvious constraints, or upstream quirks only.
- Constants, and the contents of dicts/lists that represent a fixed vocabulary
  (state values, option lists), stay alphabetically ordered where practical.
- When validation already guarantees a key exists (e.g. HA's schema validated it),
  use `data["key"]`, not `data.get("key")` — a silent `None` from `.get()` hides
  contract violations instead of surfacing them.

## 8. Testing requirements

- Every config flow branch (success, each abort/error reason, reauth, reconfigure)
  needs a test — HACS/quality-scale reviewers treat `config-flow-test-coverage` as
  a floor, not a nice-to-have. Target ~95%+ overall coverage on Silver-and-above repos.
- Use `MockConfigEntry` to set up integrations in tests; assert through `hass.states`,
  call actions through `hass.services`.
- Prefer `pytest.mark.parametrize` (with `pytest.param(..., id=...)`) over copy-pasted
  near-duplicate tests, and over `if`/`else` branching inside a single test.
- Use `@pytest.mark.usefixtures` instead of an unused fixture parameter.
- Snapshot testing (Syrupy, `.ambr` files) is fine for large structured output
  (diagnostics dumps, device/entity registries) — regenerate with `--snapshot-update`
  and review the diff before committing, don't blind-accept. Snapshots complement
  targeted assertions; they don't replace them.
- Mock all network/device I/O in unit tests — no test should touch a real device or
  the network. If you don't have a way to mock the vendor library's client yet, add
  one before adding more entity code.

## 9. `hacs.json` and HACS publishing checklist

```json
{
  "name": "Your Integration",
  "content_in_root": false,
  "homeassistant": "2025.1.0",
  "render_readme": true
}
```

Before telling a user this is "ready for HACS":

- [ ] Public GitHub repo, with a description and GitHub **topics** set (topics aren't
      shown in the HACS UI but drive search).
- [ ] `README.md` with install instructions and usage — required, not optional.
- [ ] `hacs.json` at repo root with at least `name`.
- [ ] `custom_components/<domain>/` contains a complete, valid `manifest.json` (§4).
- [ ] A `brand` entry exists (icon at minimum) — either in this repo or submitted to
      `home-assistant/brands`, per current HACS brand requirements; check hacs.xyz for
      whichever mechanism is current, this has changed over time.
- [ ] Tagged **GitHub Releases** (not just tags) with semver-ish version strings —
      HACS surfaces the 5 most recent releases to users; without releases it falls
      back to the default branch, which is a worse update experience.
- [ ] CI runs `hassfest` validation and the HACS GitHub Action (`hacs/action`) on
      every PR — add both workflows if missing.
- [ ] `strings.json` is complete and `translations/en.json` is regenerated from it
      (don't hand-edit the generated file directly and let it drift from `strings.json`).

## 10. Quality Scale — use it as your checklist, not just HA Core's

HA's Integration Quality Scale (Bronze → Silver → Gold → Platinum) is written for
Core but is the de facto quality bar the community judges any integration against,
custom or not. Treat **Bronze as the minimum for any new integration you write**, and
tell the user explicitly if you're intentionally skipping a Silver/Gold rule (e.g. no
discovery because the device has none).

- **Bronze** (baseline, ~20 rules): config flow, unique IDs, `has_entity_name`,
  `runtime_data`, test-before-setup/configure, entity-unique-id, appropriate polling
  intervals, common modules instead of copy-paste, action setup in `async_setup_entry`.
- **Silver** (reliability, ~10 rules): config entry unloading, reauth flow, entities
  marked unavailable on connection loss (with a log line on the *transition*, not
  every poll), parallel-updates declared, ≥95% test coverage, an active code owner.
- **Gold** (comprehensive, ~22 rules): discovery, diagnostics, device registry usage,
  dynamic device add/remove, stale device removal, entity/exception/icon
  translations, reconfigure flow, repair issues, full docs (use cases, supported
  devices, troubleshooting, known limitations).
- **Platinum** (excellence, 3 rules): fully async dependency, injectable
  `aiohttp`/`httpx` session (`inject-websession`), strict typing (`.strict-typing`).

If this repo ships a `quality_scale.yaml`, keep it in sync with what you actually
implement — don't claim a tier the code doesn't meet.

## 11. Diagnostics & error handling

- Implement `diagnostics.py` (`async_get_config_entry_diagnostics`) and **redact**
  anything sensitive — API keys, tokens, precise GPS coordinates, serial numbers if
  the user could be identified by them — using `homeassistant.components.diagnostics.util.async_redact_data`.
- Availability: entities go unavailable on connection loss and recover automatically
  when the coordinator succeeds again; log the *state transition*, not a line per
  failed poll (that floods the log).
- User-facing errors from service actions/config flow must be translatable
  (`translation_key` + `strings.json` entries), not raw exception text.

## 12. Git / PR workflow discipline

- Don't amend, squash, or rebase commits already pushed to an open PR branch —
  reviewers rely on being able to see exactly what changed since their last look.
- If a PR template exists (`.github/PULL_REQUEST_TEMPLATE.md`), use it verbatim.
  Leave unchecked boxes unchecked and in place; don't delete template sections.
- Never force-push over shared branches, never skip commit hooks, never commit
  without being asked to (see §2).
- Flag breaking changes explicitly and get confirmation before implementing:
  entity ID changes, unique ID changes, config entry data schema changes, state
  value/unit changes, device class changes, service action signature changes. Use
  a repair issue + `strings.json` + a deprecation window where the ecosystem
  convention calls for one, rather than a silent break.

## 13. Security checklist

- No credentials, tokens, or API keys committed anywhere — including in test
  fixtures. Use `MockConfigEntry` with obviously-fake values (`"token": "test-token"`).
- No credentials in log output at any log level, including `debug`.
- Validate and sanitize anything derived from user input before using it in a
  filesystem path, shell command, or URL — this applies even inside a "trusted"
  local integration.
- Third-party libraries must be OSI-licensed and pulled from PyPI, not vendored
  copies of someone else's unlicensed code.

## 14. Common pitfalls (fix these on sight)

| Pitfall | Why it matters |
|---|---|
| Polling faster than the device/API needs | Fails `appropriate-polling`, can get your integration rate-limited or banned by the vendor API |
| `unique_id` derived from IP/hostname | Breaks the moment DHCP reassigns the address; fails `entity-unique-id` intent |
| Entity name repeats the device name ("Living Room Light Power") | `has_entity_name` violation; HA already prefixes the device name |
| Blocking calls (`requests`, `time.sleep`) inside `async def` | Blocks the event loop for every entity in the instance, not just yours |
| Catching `Exception` broadly and logging-and-continuing | Hides real failures from `test-before-setup` / `action-exceptions` expectations |
| YAML-only setup for a new integration | Config flow is mandatory for anything new |
| Multiple integrations in one HACS repo | HACS expects one `custom_components/<domain>/` per repo |
| Hand-editing `translations/en.json` directly | Gets overwritten/drifts from `strings.json`, the actual source of truth |
| Committing without being asked | See §2 — prepare and explain, then wait for approval |

## 15. Sources

- [Home Assistant Developer Docs — Creating your first integration](https://developers.home-assistant.io/docs/creating_component_index/)
- [Home Assistant Developer Docs — Development checklist](https://developers.home-assistant.io/docs/development_checklist/)
- [Home Assistant Developer Docs — Style guidelines](https://developers.home-assistant.io/docs/development_guidelines/)
- [Home Assistant Developer Docs — Integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Home Assistant Developer Docs — Quality scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
- [Home Assistant Developer Docs — Third-party client libraries](https://developers.home-assistant.io/docs/api_lib_index/)
- [Home Assistant Developer Docs — Entity naming (has_entity_name)](https://developers.home-assistant.io/docs/core/entity/)
- [Home Assistant Developer Docs — Config flow handler](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Home Assistant Developer Docs — Testing your code](https://developers.home-assistant.io/docs/development_testing/)
- [Home Assistant Developer Docs — Open Home Foundation AI policy](https://developers.home-assistant.io/blog/2026/07/20/ai-policy/)
- [home-assistant/core AGENTS.md](https://github.com/home-assistant/core/blob/dev/AGENTS.md)
- [HACS — General publishing requirements](https://www.hacs.xyz/docs/publish/start/)
- [HACS — Integration publishing requirements](https://www.hacs.xyz/docs/publish/integration/)
- [jpawlowski/hacs.integration_blueprint — AI-enabled HA integration blueprint](https://github.com/jpawlowski/hacs.integration_blueprint)
- [ludeeus/integration_blueprint — canonical HACS integration blueprint](https://github.com/ludeeus/integration_blueprint)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
- [agents.md — the AGENTS.md open format](https://agents.md/)
