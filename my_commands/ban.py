import discord
from discord import app_commands
import re
import asyncio
from utils.db_helpers import get_user, get_banned_user

ban_group = app_commands.Group(
    name="ban", description="Ban, unban, and list banned players."
)


@ban_group.command()
@app_commands.describe(
    player="Which player?",
)
async def issue(interaction: discord.Interaction, player: str):
    """Ban a player."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    await interaction.response.defer()

    the_user = await get_user(player)
    if not the_user:
        await interaction.followup.send("User not found")
        return

    id = the_user[11]
    server_cmd = f"banid {id}"
    cmd = [
        "runuser",
        "pzserver",
        "-c",
        f"/home/pzserver/pzserver send '{server_cmd}'",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except asyncio.SubprocessError as e:
        print(f"Subprocess error occurred: {e}")

    print(output.decode())
    print(error.decode())

    banned_player = await get_banned_user(id)
    msg = (
        f"Player **{player}** has been **banned** from the "
        "Zomboid server\n"
        f"Username: {player}\n"
        f"SteamID: {id}"
        if banned_player is not None
        else "Command was sent but user not found in bannedid's db. What happen?"
    )
    await interaction.followup.send(msg)


@ban_group.command()
@app_commands.describe(
    player="Which player?",
)
async def revoke(interaction: discord.Interaction, player: str):
    """Un-Ban a player."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    await interaction.response.defer()

    the_user = await get_user(player)
    if not the_user:
        await interaction.followup.send("User not found")
        return

    id = the_user[11]
    server_cmd = f"unbanid {id}"
    cmd = [
        "runuser",
        "pzserver",
        "-c",
        f"/home/pzserver/pzserver send '{server_cmd}'",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except asyncio.SubprocessError as e:
        print(f"Subprocess error occurred: {e}")

    print(output.decode())
    print(error.decode())

    banned_player = await get_banned_user(id)
    msg = (
        f"Player **{player}** has been **UN-banned** from the " "Zomboid server"
        if banned_player is None
        else "Command was sent but user is still in the bannedid's db. What happen?"
    )
    await interaction.followup.send(msg)
