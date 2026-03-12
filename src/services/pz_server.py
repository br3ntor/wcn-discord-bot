import asyncio
import logging
import re

from rcon.source import rcon

from src.config import Config
from src.services.server import get_game_version

logger = logging.getLogger(__name__)


async def pz_send_command(system_user: str, server_command: str) -> str | None:
    """Sends a command to the game-server via RCON."""
    server_config = Config.get_rcon_config_by_user(system_user)
    if not server_config:
        logger.error(f"No server config found for user: {system_user}")
        return None

    rcon_config = server_config.get("rcon", {})
    if not rcon_config.get("password"):
        logger.error(f"RCON password not configured for server: {system_user}")
        return None

    rcon_host = rcon_config.get("host", "127.0.0.1")
    rcon_port = rcon_config.get("port", 27016)
    rcon_password = rcon_config.get("password", "")

    try:
        response = await asyncio.wait_for(
            rcon(
                server_command,
                host=rcon_host,
                port=rcon_port,
                passwd=rcon_password,
            ),
            timeout=10.0,
        )
        logger.debug("Response: %s", response)
        return str(response).strip()
    except asyncio.TimeoutError:
        logger.error(
            f"RCON timeout connecting to {system_user} at {rcon_host}:{rcon_port}"
        )
        return None
    except ConnectionRefusedError:
        logger.error(
            f"RCON connection refused - is server running and RCON enabled for {system_user}?"
        )
        return None
    except Exception as e:
        logger.error(f"RCON error for {system_user}: {e}")
        return None


async def pz_send_message(server: str, message: str) -> bool:
    """Sends a correctly formatted message to the game-server."""
    valid_msg = re.sub(r"[\"']", "", message)
    server_msg = f'servermsg "{valid_msg}"'
    return await pz_send_command(server, server_msg) is not None


def _is_player_not_found(response: str, player: str) -> bool:
    return f"User {player} not found." in response


def _is_godmode_enabled(response: str, player: str) -> bool:
    return f"User {player} is now invincible." in response


def _is_godmode_disabled(response: str, player: str) -> bool:
    off_strings = (
        f"User {player} is no more invincible.",
        f"User {player} is no longer invincible.",
    )
    return any(message in response for message in off_strings)


def _is_ban_success(response: str, steam_id: str) -> bool:
    success_strings = (
        f"SteamID {steam_id} is now banned",
        f"System banned SteamID {steam_id}",
    )
    return any(message in response for message in success_strings)


def _is_unban_success(response: str, steam_id: str) -> bool:
    return f"SteamID {steam_id} is now unbanned" in response


def _is_player_lookup_failure(response: str) -> bool:
    failure_strings = (
        "Can't find player",
        "No such user",
    )
    return any(message in response for message in failure_strings)


def _is_teleport_success(response: str, player1: str, player2: str) -> bool:
    return f"teleported {player1} to {player2}" in response


def _is_add_xp_success(response: str, player: str, skill: str) -> bool:
    return response.startswith("Added ") and f" {skill} xp's to {player}" in response


def _is_set_access_level_success(response: str, player: str, access_level: str) -> bool:
    expected_responses = {
        "admin": f"User {player} is now admin",
        "user": f"User {player} is now user",
        "none": f"User {player} no longer has access level",
    }
    expected_response = expected_responses.get(access_level)
    return expected_response is not None and expected_response in response


def _is_setpassword_b42_success(response: str) -> bool:
    return response.startswith("Your new password is ")


def _is_remove_user_success(response: str, player: str) -> bool:
    return f"User {player} removed from white list" in response


def _is_add_user_success(response: str, player: str) -> bool:
    return f"User {player} created with the password " in response


async def pz_heal_player(server: str, player: str) -> tuple[bool, str]:
    """Heals a player by toggling godmode on and off via RCON."""
    version = get_game_version(server)

    if version == "B42":
        god_on = f'godmodeplayer "{player}" -true'
        god_off = f'godmodeplayer "{player}" -false'
    else:
        god_on = f'godmode "{player}" -true'
        god_off = f'godmode "{player}" -false'

    god_on_response = await pz_send_command(server, god_on)
    if god_on_response is None:
        return False, "Could not reach the server via RCON."

    if _is_player_not_found(god_on_response, player):
        return False, god_on_response

    if not _is_godmode_enabled(god_on_response, player):
        logger.error("Unexpected godmode enable response: %s", god_on_response)
        return False, f"Unexpected server response: {god_on_response}"

    await asyncio.sleep(0.2)
    god_off_response = await pz_send_command(server, god_off)
    if god_off_response is None:
        return False, "Could not reach the server via RCON."

    if _is_player_not_found(god_off_response, player):
        return False, god_off_response

    if not _is_godmode_disabled(god_off_response, player):
        logger.error("Unexpected godmode disable response: %s", god_off_response)
        return False, f"Unexpected server response: {god_off_response}"

    return True, god_off_response


async def pz_ban_player(server: str, steam_id: str) -> tuple[bool, str]:
    """Bans a player by SteamID via RCON."""
    response = await pz_send_command(server, f"banid {steam_id}")
    if response is None:
        return False, "Could not reach the server via RCON."

    if not _is_ban_success(response, steam_id):
        logger.error("Unexpected ban response: %s", response)
        return False, f"Unexpected server response: {response}"

    return True, response


async def pz_unban_player(server: str, steam_id: str) -> tuple[bool, str]:
    """Unbans a player by SteamID via RCON."""
    response = await pz_send_command(server, f"unbanid {steam_id}")
    if response is None:
        return False, "Could not reach the server via RCON."

    if not _is_unban_success(response, steam_id):
        logger.error("Unexpected unban response: %s", response)
        return False, f"Unexpected server response: {response}"

    return True, response


async def pz_add_xp(
    server: str, player: str, skill: str, amount: int
) -> tuple[bool, str]:
    """Adds XP to a player via RCON."""
    response = await pz_send_command(server, f'addxp "{player}" {skill}={amount}')
    if response is None:
        return False, "Could not reach the server via RCON."

    if _is_player_lookup_failure(response):
        return False, response

    if not _is_add_xp_success(response, player, skill):
        logger.error("Unexpected addxp response: %s", response)
        return False, f"Unexpected server response: {response}"

    return True, response


async def pz_set_access_level(
    server: str, player: str, access_level: str
) -> tuple[bool, str]:
    """Sets a player's access level via RCON."""
    response = await pz_send_command(
        server, f'setaccesslevel "{player}" "{access_level}"'
    )
    if response is None:
        return False, "Could not reach the server via RCON."

    if not _is_set_access_level_success(response, player, access_level):
        logger.error("Unexpected setaccesslevel response: %s", response)
        return False, f"Unexpected server response: {response}"

    return True, response


async def pz_setpassword_b42(
    server: str, player: str, new_password: str
) -> tuple[bool, str]:
    """Sets a B42 player's password via RCON."""
    response = await pz_send_command(server, f'setpassword "{player}" "{new_password}"')
    if response is None:
        return False, "Could not reach the server via RCON."

    if not _is_setpassword_b42_success(response):
        logger.error("Unexpected setpassword response: %s", response)
        return False, f"Unexpected server response: {response}"

    return True, response


async def pz_reset_password_b41(
    server: str, player: str, new_password: str
) -> tuple[bool, str]:
    """Resets a B41 player's password by recreating the whitelist entry via RCON."""
    remove_response = await pz_send_command(
        server, f'removeuserfromwhitelist "{player}"'
    )
    if remove_response is None:
        return False, "Could not reach the server via RCON."

    if not _is_remove_user_success(remove_response, player):
        logger.error("Unexpected removeuserfromwhitelist response: %s", remove_response)
        return False, f"Unexpected server response: {remove_response}"

    await asyncio.sleep(0.2)
    add_response = await pz_send_command(server, f'adduser "{player}" "{new_password}"')
    if add_response is None:
        return False, "Could not reach the server via RCON."

    if not _is_add_user_success(add_response, player):
        logger.error("Unexpected adduser response: %s", add_response)
        return False, f"Unexpected server response: {add_response}"

    return True, add_response


async def pz_teleport_player(
    server: str, player1: str, player2: str
) -> tuple[bool, str]:
    """Teleport player1 to player2. Command varies by game version."""
    version = get_game_version(server)

    if version == "B42":
        command = f'teleportplayer "{player1}" "{player2}"'
    else:
        command = f'teleport "{player1}" "{player2}"'

    response = await pz_send_command(server, command)
    if response is None:
        return False, "Could not reach the server via RCON."

    if _is_player_lookup_failure(response):
        return False, response

    if not _is_teleport_success(response, player1, player2):
        logger.error("Unexpected teleport response: %s", response)
        return False, f"Unexpected server response: {response}"

    return True, response
