import asyncio
import re

import discord
from discord import app_commands
from tabulate import tabulate

from config import LOCAL_SERVER_NAMES
from utils.db_helpers import (
    get_all_banned_users,
    get_banned_user,
    get_user,
    get_user_by_steamid,
)

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


def format_message(banned_table: list, server: str) -> str:
    msg = f"""**{server} Server Bans:**
```md
{tabulate(banned_table, headers=["Name", "SteamID"])}
```
"""
    return msg


@ban_group.command()
async def list(interaction: discord.Interaction):
    """Retrieve a list of all banned players across servers."""
    await interaction.response.defer()

    # We will build three inputs for our format_message function
    banned_lists = {"pel_pzserver": [], "medium_pzserver": [], "heavy_pzserver": []}

    # Really what I should do is query with all the banned
    # usernames collected first, not make a call for each one in a loop
    for server in LOCAL_SERVER_NAMES:

        servers_banned_players = await get_all_banned_users(server)
        print(server)
        print(servers_banned_players)

        if not servers_banned_players:
            continue

        banned_players = []
        # Banned players tend to get multiple db entries but
        # we only need one so if a player is already processed well skip dupes
        seen_players = []
        for b_player in servers_banned_players:
            steamid = b_player[0]

            if steamid in seen_players:
                print(f"{steamid} seen in seen_players")
                continue

            seen_players.append(steamid)

            # Lets see if we can get name of the banned player
            # which well use to create the data object we want
            user = await get_user_by_steamid(server, steamid)
            if not user:
                print(
                    "User banned but not in whitelist, banned before joined server prob..."
                )
                banned_players.append(("None", steamid))
                continue
            elif isinstance(user, str):
                print(user)
                continue

            print(user)
            banned_players.append((user[2], steamid))

        print(f"For the {server} server:")
        print(banned_players)
        banned_lists[server].extend(banned_players)

    banned_light = [[p[0], p[1]] for p in banned_lists["pel_pzserver"]]
    banned_medium = [[p[0], p[1]] for p in banned_lists["medium_pzserver"]]
    banned_heavy = [[p[0], p[1]] for p in banned_lists["heavy_pzserver"]]

    formatted_light = format_message(banned_light, "Light")
    formatted_medium = format_message(banned_medium, "Medium")
    formatted_heavy = format_message(banned_heavy, "Heavy")

    output = (
        "*If the players name is None then they were banned before ever joining.\n"
        f"{formatted_light}{formatted_medium}{formatted_heavy}"
    )

    await interaction.followup.send(output)
