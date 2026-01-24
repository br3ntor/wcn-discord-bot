import asyncio
import re


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
        # Create the subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        # Get the output of the subprocess
        output, error = await process.communicate()

        if process.returncode != 0:
            print(f"Error: {error.decode().strip()}")
            return False
        else:
            print(f"Output: {output.decode().strip()}")
            return True

    except Exception as e:
        print(f"Subprocess error occurred: {e}")
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
    # Wrapping arguments in double quotes as per PZ documentation requirements
    server_command = f'setpassword "{player}" "{new_password}"'
    return await pz_send_command(server, server_command)
