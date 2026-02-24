import asyncio
import configparser
import logging
import os

from src.config import Config

logger = logging.getLogger(__name__)

SERVER_DATA = Config.SERVER_DATA
SERVER_NAMES = Config.SERVER_NAMES


async def server_isrunning(server: str) -> bool:
    """Check if the given zomboid server name is running"""
    cmd = [
        "ps",
        "-f",
        "-u",
        server,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        output, error = await process.communicate()

    except Exception as e:
        logger.error(f"Subprocess error occurred: {e}")

    out, err = output.decode(), error.decode()

    if err:
        logger.warning(err)

    for line in out.splitlines():
        if "ProjectZomboid64" in line:
            logger.info(f"{server} is running:\n{line}")
            return True

    return False


async def server_setting_paths() -> list:
    """Return list of paths to running servers settings files"""
    server_files = []
    servers_with_gists = [
        server["system_user"] for server in SERVER_DATA if server["gists"]
    ]
    for username in servers_with_gists:
        if await server_isrunning(username):
            server_files.append(f"/home/{username}/Zomboid/Server/pzserver.ini")
    return server_files


async def get_servers_workshop_ids(
    file_paths: list[str],
) -> dict[str, list[str]]:
    """
    Returns running server names (which are the usernames) with their workshop ids.
    Assumes the file path is like '/home/{username}/Zomboid/Server/pzserver.ini'.
    """

    logger.info(f"Processing server config files from paths: {file_paths}")
    servers_workshopids_lists: dict[str, list[str]] = {}

    for path in file_paths:
        logger.debug(f"Attempting to process file: {path}")
        server_name = ""
        try:
            parts = path.split(os.sep)
            if len(parts) > 2 and parts[1] == "home":
                server_name = parts[2]
            else:
                logger.warning(
                    f"Warning: Could not determine username from path: {path}. Skipping this file."
                )
                continue

            if not server_name:
                logger.warning(
                    f"Warning: Server name (username) is empty for path: {path}. Skipping this file."
                )
                continue

            config = configparser.ConfigParser()
            with open(path, "r") as stream:
                config.read_string("[default]\n" + stream.read())

            if "default" not in config:
                logger.warning(
                    f"Warning: '[default]' section not found in {path} for server '{server_name}'. Skipping."
                )
                continue

            workshop_items_str = config["default"].get("WorkshopItems", "")

            if not workshop_items_str:
                logger.info(
                    f"Info: No 'WorkshopItems' found or it's empty for server '{server_name}' in {path}."
                )
                continue

            workshop_ids = [
                item.strip() for item in workshop_items_str.split(";") if item.strip()
            ]

            if workshop_ids:
                servers_workshopids_lists[server_name] = workshop_ids
            else:
                logger.info(
                    f"Info: 'WorkshopItems' found but contained no valid IDs after cleaning for server '{server_name}' in {path}."
                )

        except FileNotFoundError:
            logger.error(f"Error: File not found at '{path}'. Skipping this file.")
        except IndexError:
            logger.error(
                f"Error: Path format unexpected for '{path}'. Could not extract username. Skipping."
            )
        except KeyError as e:
            logger.error(
                f"Error: Missing expected configuration key '{e}' in {path} for server '{server_name}'. Skipping."
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while processing '{path}' for server '{server_name}': {e}. Skipping."
            )

    logger.info("---")
    logger.info(
        "All collected workshop items by server (username): %s", servers_workshopids_lists
    )
    logger.info("---")
    return servers_workshopids_lists


async def servers_with_mod_update(workshop_id: str) -> list[str]:
    """Returns a list of running servers the updated mod is running on"""
    paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(paths)

    server_names = []
    for key, value in servers.items():
        if workshop_id in value:
            server_names.append(SERVER_NAMES[key])
    return server_names


async def combine_servers_workshop_ids() -> list:
    """Returns all workshop_ids together from running servers."""
    paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(paths)
    all_servers_workshop_ids = set()
    for value in servers.values():
        if value:
            all_servers_workshop_ids.update(value)

    workshop_ids = list(all_servers_workshop_ids)
    logger.info(f"Found this many workshop_ids: {len(workshop_ids)}")
    return workshop_ids


async def restart_zomboid_server(system_user: str):
    """Restarts the Project Zomboid game-server service.

    Args:
        system_user: The name of the linux user running the game server.

    """

    try:
        cmd = ["sudo", "/usr/bin/systemctl", "restart", system_user]
        process = await asyncio.create_subprocess_exec(*cmd)
        exit_code = await process.wait()
        if exit_code != 0:
            return False
    except Exception as e:
        logger.error(f"error occurred: {e}")
        return False
    return True


def get_game_version(servername: str):
    """
    Detects the PZ version based on the Java release file.
    Example path: /home/pzserver/serverfiles/jre64/release
    """
    path = f"/home/{servername}/serverfiles/jre64/release"

    if not os.path.exists(path):
        logger.warning(f"Warning: Path not found: {path}")
        return "UNKNOWN"

    try:
        with open(path, "r") as f:
            content = f.read()

            if 'JAVA_VERSION="25' in content:
                return "B42"

            elif 'JAVA_VERSION="17' in content:
                return "B41"

    except Exception as e:
        logger.error(f"Error reading release file for {servername}: {e}")

    return "UNKNOWN"
