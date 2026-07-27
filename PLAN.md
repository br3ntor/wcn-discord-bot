# Maintenance & Quality Plan

## Completed

- [x] Fix `server_isrunning` NameError on exception path + return code check
- [x] Move config init out of import time into `Config.init()` (eliminates env var read at import)
- [x] Unify duplicate `DB_PATH` (`bot_db.py` now imports from `config.py`)
- [x] Tighten `restart_zomboid_server` (stdout/stderr capture, 30s timeout, return code check)
- [x] Add `encoding="utf-8"` to all `open()` calls
- [x] Log stack trace in `on_application_command_error`
- [x] Refactor path-parsing in `get_servers_workshop_ids` / `get_servers_max_players` — username now flows through as a dict key from `server_setting_paths()`, eliminating ~30 lines of fragile `os.sep` splitting
- [x] **GitHub Actions CI** — pytest + black + ruff (mypy deferred until pre-existing type errors are fixed)
- [x] **`pyproject.toml`** — consolidate dev tool configs under one file; keep `requirements.txt` for runtime deps
- [x] **Extract INI helper** — `_read_pz_ini()` in `server.py`, replaces 3 duplicated `configparser` blocks
- [x] **Type annotations** — added full generics to public functions in `server.py`, `pz_server.py`, `steam.py`
- [x] **Black formatting** — auto-formatted entire codebase, fixed unused imports/variables/trailing whitespace

## Remaining

### Code Quality

- [ ] **Split large modules** — `ticket_watcher.py` (31KB, ~800 lines) and `bot_db.py` (738 lines)

### Database

- [x] **DB schema versioning** — init_db uses ad-hoc column checks + `DROP TABLE IF EXISTS player_command_cooldowns` on every startup. Add a `schema_version` table and make migrations explicit.
- [x] **Make DB path configurable** via env var

### Documentation

- [ ] **Document sudoers entry** for `restart_zomboid_server`
- [ ] **Make systemd unit name explicit** in `servers.json` (currently assumes `system_user == service name`)

## Notes

- Import chain: `main.py` calls `Config.init()` before `from src.bot import bot`. All downstream modules import `Config` from `sys.modules` with attributes already set. This is the key to the config refactor working.
- `server_setting_paths()` returns `dict[str, str]` (user → path). Downstream functions (`get_servers_workshop_ids`, `get_servers_max_players`) consume that dict directly.
- Tests: `pytest tests/` — 7 tests in `test_bot_db.py`, all pass.
- Bot runs with: `source .venv/bin/activate && python main.py`
