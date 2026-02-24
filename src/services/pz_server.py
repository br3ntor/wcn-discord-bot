import asyncio
import logging
import re

from src.services.server import get_game_version

logger = logging.getLogger(__name__)


async def pz_send_command(system_user: str, server_command: str):
    """Sends a command to the game-server console."""
    cmd = [
        "sudo",
        "-u",
        system_user,
        f"/home/{system_user}/pzserver",
        "send",
        f"{server_command}",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        output, error = await process.communicate()

        if process.returncode != 0:
            logger.error("Error: %s", error.decode().strip())
            return False
        else:
            logger.debug("Output: %s", output.decode().strip())
            return True

    except Exception as e:
        logger.error("Subprocess error occurred: %s", e)
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
    await asyncio.sleep(1)
    return await pz_send_command(server, blessing)


async def pz42_heal_player(server: str, player: str) -> bool:
    """Toggles godmode on a player to heal them."""
    god_on = f'godmodeplayer "{player}" -true'
    god_off = f'godmodeplayer "{player}" -false'
    if not await pz_send_command(server, god_on):
        return False
    await asyncio.sleep(1)
    return await pz_send_command(server, god_off)


async def pz_setpassword(server: str, player: str, new_password: str) -> bool:
    """Use this command to change password for a user. Use: setpassword "username" "newpassword" """
    server_command = f'setpassword "{player}" "{new_password}"'
    return await pz_send_command(server, server_command)


async def pz_teleport_player(server: str, player1: str, player2: str) -> bool:
    """Teleport player1 to player2. Command varies by game version."""
    version = get_game_version(server)

    if version == "B42":
        command = f'teleportplayer "{player1}" "{player2}"'
    else:
        command = f'teleport "{player1}" "{player2}"'

    return await pz_send_command(server, command)
