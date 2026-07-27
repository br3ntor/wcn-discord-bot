import asyncio
import configparser
import logging
from pathlib import Path

from src.config import Config

logger = logging.getLogger(__name__)

_max_players_cache: dict[str, int | None] | None = None


def get_game_db_path(system_user: str) -> Path:
    """Return the path to the PZ game database."""
    return Path(f"/home/{system_user}/Zomboid/db/pzserver.db")


def get_server_ini_path(system_user: str) -> Path:
    """Return the path to the PZ server INI settings file."""
    return Path(f"/home/{system_user}/Zomboid/Server/pzserver.ini")


def get_jre_release_path(system_user: str) -> Path:
    """Return the path to the JRE release file for version detection."""
    return Path(f"/home/{system_user}/serverfiles/jre64/release")


def get_zomboid_logs_dir(system_user: str) -> Path:
    """Return the path to the Zomboid logs directory."""
    return Path(f"/home/{system_user}/Zomboid/Logs/")


def get_serverfiles_scripts_path(system_user: str) -> Path:
    """Return the path to the serverfiles media/scripts directory."""
    return Path(f"/home/{system_user}/serverfiles/media/scripts")


def get_workshop_content_path(system_user: str) -> Path:
    """Return the path to the Steam workshop content directory."""
    return Path(f"/home/{system_user}/serverfiles/steamapps/workshop/content/108600")


def get_sandbox_vars_path(system_user: str) -> Path:
    """Return the path to the server's SandboxVars Lua file."""
    return Path(f"/home/{system_user}/Zomboid/Server/pzserver_SandboxVars.lua")


def get_item_translations_path(system_user: str) -> Path:
    """Return the path to the ItemName.json translations file."""
    return Path(f"/home/{system_user}/serverfiles/media/lua/shared/Translate/EN/ItemName.json")


async def server_isrunning(system_user: str) -> bool:
    """Check if the given zomboid server user is running."""
    cmd = [
        "ps",
        "-f",
        "-u",
        system_user,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )
        output, error = await process.communicate()
    except Exception as e:
        logger.error(f"Subprocess error occurred: {e}")
        return False

    out, err = output.decode(), error.decode()

    if err:
        logger.warning(err)

    if process.returncode and process.returncode != 0:
        logger.debug(f"ps returned non-zero: {process.returncode}")

    for line in out.splitlines():
        if "ProjectZomboid64" in line:
            return True

    return False


def _read_pz_ini(path: str) -> configparser.ConfigParser:
    """Read a PZ server INI file.

    PZ INI files are flat key=value pairs with no section header.
    This prepends a synthetic [default] section so configparser can parse them.
    """
    config = configparser.ConfigParser()
    with open(path, "r", encoding="utf-8") as stream:
        config.read_string("[default]\n" + stream.read())
    return config


def get_workshop_ids_for_server(system_user: str) -> set[str]:
    """Reads WorkshopItems from a server's INI file and returns the set of active workshop IDs."""
    ini_path = get_server_ini_path(system_user)
    try:
        config = _read_pz_ini(ini_path)
        workshop_items_str = config["default"].get("WorkshopItems", "")
        if not workshop_items_str:
            return set()

        return {item.strip() for item in workshop_items_str.split(";") if item.strip()}
    except FileNotFoundError:
        logger.warning(f"Server INI not found at '{ini_path}'")
        return set()
    except Exception as e:
        logger.error(f"Error reading WorkshopItems for {system_user}: {e}")
        return set()


async def server_setting_paths() -> dict[str, str]:
    """Return mapping of system_user to ini path for running servers with gists."""
    user_paths: dict[str, str] = {}
    servers_with_gists = [
        server["system_user"] for server in Config.SERVER_DATA if server["gists"]
    ]
    for username in servers_with_gists:
        if await server_isrunning(username):
            user_paths[username] = str(get_server_ini_path(username))
    return user_paths


async def get_servers_workshop_ids(
    user_paths: dict[str, str],
) -> dict[str, list[str]]:
    """Returns running server names (usernames) with their workshop ids."""

    logger.debug(f"Processing server config files: {user_paths}")
    servers_workshopids_lists: dict[str, list[str]] = {}

    for system_user, path in user_paths.items():
        logger.debug(f"Attempting to process file for {system_user}: {path}")
        try:
            config = _read_pz_ini(path)

            if "default" not in config:
                logger.warning(
                    f"Warning: '[default]' section not found in {path} for {system_user}. Skipping."
                )
                continue

            workshop_items_str = config["default"].get("WorkshopItems", "")

            if not workshop_items_str:
                logger.debug(
                    f"No 'WorkshopItems' found or it's empty for {system_user} in {path}."
                )
                continue

            workshop_ids = [
                item.strip() for item in workshop_items_str.split(";") if item.strip()
            ]

            if workshop_ids:
                servers_workshopids_lists[system_user] = workshop_ids
            else:
                logger.debug(
                    f"'WorkshopItems' found but contained no valid IDs after cleaning for {system_user} in {path}."
                )

        except FileNotFoundError:
            logger.error(f"Error: File not found at '{path}'. Skipping this file.")
        except KeyError as e:
            logger.error(
                f"Error: Missing expected configuration key '{e}' in {path} for {system_user}. Skipping."
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while processing '{path}' for {system_user}: {e}. Skipping."
            )

    return servers_workshopids_lists


async def servers_with_mod_update(workshop_id: str) -> list[str]:
    """Returns a list of running servers the updated mod is running on"""
    user_paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(user_paths)

    server_names = []
    for key, value in servers.items():
        if workshop_id in value:
            server_names.append(Config.SERVER_NAMES[key])
    return server_names


async def combine_servers_workshop_ids() -> list[str]:
    """Returns all workshop_ids together from running servers."""
    user_paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(user_paths)
    all_servers_workshop_ids = set()
    for value in servers.values():
        if value:
            all_servers_workshop_ids.update(value)

    workshop_ids = list(all_servers_workshop_ids)
    logger.debug(f"Found this many workshop_ids: {len(workshop_ids)}")
    return workshop_ids


async def restart_zomboid_server(system_user: str) -> bool:
    """Restarts the Project Zomboid game-server service.

    Args:
        system_user: The name of the linux user running the game server.

    """

    try:
        cmd = ["sudo", "/usr/bin/systemctl", "restart", system_user]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=30.0
        )
        if process.returncode and process.returncode != 0:
            logger.error(
                f"systemctl restart failed for {system_user} "
                f"(rc={process.returncode}): {stderr.decode().strip()}"
            )
            return False
        return True
    except asyncio.TimeoutError:
        logger.error(f"systemctl restart timed out for {system_user}")
        return False
    except Exception as e:
        logger.error(f"restart_zomboid_server error: {e}")
        return False


def get_game_version(system_user: str) -> str:
    """Detect the PZ version based on the Java release file."""
    path = get_jre_release_path(system_user)

    if not path.exists():
        logger.warning(f"Warning: Path not found: {path}")
        return "UNKNOWN"

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

            if 'JAVA_VERSION="25' in content:
                return "B42"

            elif 'JAVA_VERSION="17' in content:
                return "B41"

    except Exception as e:
        logger.error(f"Error reading release file for {system_user}: {e}")

    return "UNKNOWN"


async def get_servers_max_players(user_paths: dict[str, str]) -> dict[str, int | None]:
    """
    Returns dict mapping server names (usernames) to their MaxPlayers setting.
    Returns None if not found or on error.

    Cached until bot restarts.
    """
    global _max_players_cache

    if _max_players_cache is not None:
        return _max_players_cache

    servers_max_players: dict[str, int | None] = {}

    for system_user, path in user_paths.items():
        try:
            config = _read_pz_ini(path)

            if "default" in config:
                max_players = config["default"].getint("MaxPlayers", None)
                servers_max_players[system_user] = max_players
            else:
                servers_max_players[system_user] = None

        except FileNotFoundError:
            logger.error(f"File not found at '{path}'. MaxPlayers will be unknown.")
            servers_max_players[system_user] = None
        except Exception as e:
            logger.error(
                f"Error reading MaxPlayers from '{path}': {e}. MaxPlayers will be unknown."
            )
            servers_max_players[system_user] = None

    _max_players_cache = servers_max_players
    return servers_max_players
