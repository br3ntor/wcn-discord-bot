import asyncio
import re

import discord
from discord import app_commands

from config import LOCAL_SERVER_NAMES
from utils.db_helpers import get_banned_user, get_user

ban_group = app_commands.Group(
    name="ban", description="Ban, unban, and list banned players."
)


@ban_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(LOCAL_SERVER_NAMES)
    ]
)
@app_commands.describe(
    server="Which server?",
    player="Which player?",
)
async def issue(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Ban a player."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    await interaction.response.defer()

    the_user = await get_user(server.name, player)
    if not the_user:
        await interaction.followup.send("User not found")
        return
    elif isinstance(the_user, str):
        await interaction.followup.send(the_user)
        return

    id: str = the_user[11]
    server_cmd = f"banid {id}"
    cmd = [
        "runuser",
        f"{server.name}",
        "-c",
        f"/home/{server.name}/pzserver send '{server_cmd}'",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except Exception as e:
        print(f"Subprocess error occurred: {e}")

    print(output.decode())
    print(error.decode())

    banned_player = await get_banned_user(server.name, id)

    if banned_player is None:
        msg = f"Command was sent but user **{player}** not found in bannedid's db. What happen?"
        await interaction.followup.send(msg)
    elif len(banned_player) > 0 and banned_player[0] == id:
        msg = (
            f"Player **{player}** has been **banned** from the "
            f"**{server.name}** server.\n"
            f"Username: {player}\n"
            f"SteamID: {id}"
        )
        await interaction.followup.send(msg)
    elif isinstance(banned_player, str):
        await interaction.followup.send(banned_player)
    else:
        await interaction.followup.send("An unexpected value was returned.")


@ban_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(LOCAL_SERVER_NAMES)
    ]
)
@app_commands.describe(
    server="Which server?",
    player="Which player?",
)
async def revoke(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Un-Ban a player."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    await interaction.response.defer()

    the_user = await get_user(server.name, player)
    if not the_user:
        await interaction.followup.send("User not found")
        return
    elif isinstance(the_user, str):
        await interaction.followup.send(the_user)
        return

    id = the_user[11]
    server_cmd = f"unbanid {id}"
    cmd = [
        "runuser",
        f"{server.name}",
        "-c",
        f"/home/{server.name}/pzserver send '{server_cmd}'",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except Exception as e:
        print(f"Subprocess error occurred: {e}")

    print(output.decode())
    print(error.decode())

    banned_player = await get_banned_user(server.name, id)
    msg = (
        f"Player **{player}** has been **UN-banned** from the **{server.name}** server"
        if banned_player is None
        else "Command was sent but user is still in the bannedid's db. What happen?"
    )
    await interaction.followup.send(msg)
