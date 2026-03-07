import asyncio
import logging
import re

from rcon.source import rcon

from src.config import Config

logger = logging.getLogger(__name__)


async def pz_send_command(system_user: str, server_command: str):
    """Sends a command to the game-server via RCON."""
    server_config = Config.get_rcon_config_by_user(system_user)
    if not server_config:
        logger.error(f"No server config found for user: {system_user}")
        return False

    rcon_config = server_config.get("rcon_password")
    if not rcon_config:
        logger.error(f"RCON password not configured for server: {system_user}")
        return False

    rcon_host = server_config.get("rcon_host", "127.0.0.1")
    rcon_port = server_config.get("rcon_port", 27016)
    rcon_password = server_config.get("rcon_password", "")

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
        return True
    except asyncio.TimeoutError:
        logger.error(
            f"RCON timeout connecting to {system_user} at {rcon_host}:{rcon_port}"
        )
        return False
    except ConnectionRefusedError:
        logger.error(
            f"RCON connection refused - is server running and RCON enabled for {system_user}?"
        )
        return False
    except Exception as e:
        logger.error(f"RCON error for {system_user}: {e}")
        return False


async def pz_send_message(server: str, message: str) -> bool:
    """Sends a correctly formatted message to the game-server."""
    valid_msg = re.sub(r"[\"']", "", message)
    server_msg = f'servermsg "{valid_msg}"'
    return await pz_send_command(server, server_msg)


async def pz_heal_player(server: str, player: str) -> bool:
    """Toggles godmode on a player to heal them."""
    blessing = f'godmode "{player}"'
    if not await pz_send_command(server, blessing):
        return False
    return await pz_send_command(server, blessing)


async def pz42_heal_player(server: str, player: str) -> bool:
    """Toggles godmode on a player to heal them."""
    god_on = f'godmodeplayer "{player}" -true'
    god_off = f'godmodeplayer "{player}" -false'
    if not await pz_send_command(server, god_on):
        return False
    return await pz_send_command(server, god_off)


async def pz_setpassword(server: str, player: str, new_password: str) -> bool:
    """Use this command to change password for a user. Use: setpassword "username" "newpassword" """
    server_command = f'setpassword "{player}" "{new_password}"'
    return await pz_send_command(server, server_command)


async def pz_teleport_player(server: str, player1: str, player2: str) -> bool:
    """Teleport player1 to player2. Command varies by game version."""
    from src.services.server import get_game_version

    version = get_game_version(server)

    if version == "B42":
        command = f'teleportplayer "{player1}" "{player2}"'
    else:
        command = f'teleport "{player1}" "{player2}"'

    return await pz_send_command(server, command)
