# WCN Discord Bot

## Running the Bot

```bash
# Activate venv first
source .venv/bin/activate

# Run
python main.py
```

Requires environment variables in `.env` (see `.env.example`):
- `DISCORD_TOKEN` (required)
- `ANNOUNCE_CHANNEL`, `MY_GUILD`, `PZ_ADMIN_ROLE_ID`, `MOD_CHANNEL` (required)

## Lint / Typecheck / Test

```bash
.venv/bin/ruff check .
.venv/bin/black --check .
.venv/bin/mypy <scoped paths>
.venv/bin/pytest
```

mypy has pre-existing errors repo-wide (see TODO in `pyproject.toml`) — check only the files you touched, not the whole tree.

## Project Structure

- **Entry point**: `main.py` loads config, then `src/bot.py`
- **Bot class**: `src/bot.py` - `WCNBot` extends `commands.Bot`, uses discord.py 2.7
- **Cogs**: `src/bot_cogs/*/*.py` - dynamically loaded from `config/cogs.json`
- **Features**: `src/features/*.py` - utility features (auto_restart, godmode, skill_restore, teleport)
- **Services**: `src/services/*.py` - PZ server, Steam, Workshop, PocketBase, DB, etc.
- **Config files**: `config/servers.json`, `config/cogs.json` (both gitignored; tracked example files `config/servers.json.example`, `config/cogs.json.example`)

## Enabling/Disabling Cogs

Edit `config/cogs.json` - set `"enabled": true|false`. Bot loads cogs at startup based on this config.

`config/cogs.json` is gitignored. Copy it from the tracked example on a fresh checkout:

```bash
cp config/cogs.json.example config/cogs.json
```

Because real configs are not tracked, **new cogs must be added to `config/cogs.json.example` in the same change that adds the cog** - existing copies will not pick them up automatically. If `config/cogs.json` is missing, the loader warns and starts the bot with no cogs.

## Server Configuration

`config/servers.json` defines each PZ server with:
- `system_user`: Linux user running the server
- `port`: game port
- `rcon`: {host, port, password}
- `discord_playerlist`: thread_id, message_id
- `save_name` (optional): PZ save folder name under `Zomboid/Saves/Multiplayer/`, defaults to `pzserver`. Its folder creation time is tracked in the `server_worlds` table and used to scope command stats to the current game world.

## Key Dependencies

- discord.py==2.7.1
- aiosqlite, aiohttp, rcon, python-a2s (server queries)
- Dev tools (`requirements-dev.txt`): ruff, black, mypy, pytest