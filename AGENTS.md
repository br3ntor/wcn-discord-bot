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

## Project Structure

- **Entry point**: `main.py` loads config, then `src/bot.py`
- **Bot class**: `src/bot.py` - `WCNBot` extends `commands.Bot`, uses discord.py 2.6
- **Cogs**: `src/bot_cogs/*/*.py` - dynamically loaded from `config/cogs.json`
- **Features**: `src/features/*.py` - utility features (auto_restart, godmode, skill_restore, teleport)
- **Services**: `src/services/*.py` - PZ server, Steam, Workshop, PocketBase, DB, etc.
- **Config files**: `config/servers.json`, `config/cogs.json` (both gitignored)

## Enabling/Disabling Cogs

Edit `config/cogs.json` - set `"enabled": true|false`. Bot loads cogs at startup based on this config.

## Server Configuration

`config/servers.json` defines each PZ server with:
- `system_user`: Linux user running the server
- `port`: game port
- `rcon`: {host, port, password}
- `discord_playerlist`: thread_id, message_id

## Key Dependencies

- discord.py==2.6.4
- aiosqlite, aiohttp, rcon, python-a2s (server queries)