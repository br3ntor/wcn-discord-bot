import asyncio
import re

import discord
from discord import app_commands
from tabulate import tabulate

from config import Config
from lib.game_db import (
    get_all_banned_players,
    get_banned_player,
    get_player,
    get_player_by_steamid,
)
from lib.pzserver import pz_send_command
from lib.server_utils import server_isrunning

ban_group = app_commands.Group(
    name="ban", description="Ban, unban, and list banned players."
)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


async def wait_for_ban_issue(system_user, player_id, max_attempts=5, delay=0.5):
    for attempt in range(max_attempts):
        print("Attempt:", attempt)
        banned_player = await get_banned_player(system_user, player_id)
        if banned_player and len(banned_player) > 0 and banned_player[0] == player_id:
            return banned_player
        await asyncio.sleep(delay)
    return None


async def wait_for_ban_removal(system_user, player_id, max_attempts=5, delay=0.5):
    for attempt in range(max_attempts):
        print("Attempt:", attempt)
        banned_player = await get_banned_player(system_user, player_id)
        if banned_player and len(banned_player) > 0 and banned_player[0] == player_id:
            await asyncio.sleep(delay)
            continue
        return None


@ban_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(
    server="Which server?",
    player="Enter player's name or SteamID.",
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def issue(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    player: str,
):
    """Ban a player by name or SteamID."""
    player_input = player.strip()

    if re.search(r"[\"']", player_input):
        await interaction.response.send_message("Quotes are not allowed.")
        return

    await interaction.response.defer()
    system_user = SYSTEM_USERS[server.name]

    # Determine if input is a SteamID
    if player_input.isdigit():
        steam_id = player_input
        row = await get_player_by_steamid(system_user, steam_id)
        player_name = row[2] if row else None
    else:
        # Lookup player by name
        player_row = await get_player(system_user, player_input)

        if isinstance(player_row, str):
            await interaction.followup.send(player_row)
            return
        if not player_row:
            await interaction.followup.send(
                f"No player found with name **{player_input}**."
            )
            return

        steam_id = player_row[11]
        player_name = player_input

    # Check if the game server is running
    if not await server_isrunning(system_user):
        await interaction.followup.send(f"**{server.name}** is **NOT** running!")
        return

    # Issue the ban command
    server_cmd = f"banid {steam_id}"
    await pz_send_command(system_user, server_cmd)

    banned_player = await wait_for_ban_issue(system_user, steam_id)

    # Construct response
    if banned_player is None:
        msg = (
            f"Ban command sent, but SteamID **{steam_id}** not found in banned list.\n"
            f"Player input was: **{player_input}**"
        )
    elif isinstance(banned_player, str):
        msg = banned_player
    elif len(banned_player) > 0 and banned_player[0] == steam_id:
        msg = (
            f"Player has been **banned** from the **{server.name}** server.\n"
            f"Username: **{player_name or '(unknown)'}**\n"
            f"SteamID: **{steam_id}**"
        )
    else:
        msg = "An unexpected result occurred when checking the ban status."

    await interaction.followup.send(msg)


@ban_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(
    server="Which server?",
    player="Enter player's name or SteamID.",
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def revoke(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    player: str,
):
    """Unban a player by name or SteamID."""
    player_input = player.strip()

    if re.search(r"[\"']", player_input):
        await interaction.response.send_message("Quotes are not allowed.")
        return

    await interaction.response.defer()
    system_user = SYSTEM_USERS[server.name]

    # Determine if input is a SteamID
    if player_input.isdigit():
        steam_id = player_input
        row = await get_player_by_steamid(system_user, steam_id)
        player_name = row[2] if row else None
    else:
        player_row = await get_player(system_user, player_input)

        if isinstance(player_row, str):
            await interaction.followup.send(player_row)
            return
        if not player_row:
            await interaction.followup.send(
                f"No player found with name **{player_input}**."
            )
            return

        steam_id = player_row[11]
        player_name = player_input

    # Send unban command
    server_cmd = f"unbanid {steam_id}"
    await pz_send_command(system_user, server_cmd)

    banned_player = await wait_for_ban_removal(system_user, steam_id)

    if banned_player is None:
        msg = (
            f"Player has been **unbanned** from the **{server.name}** server.\n"
            f"Username: **{player_name or '(unknown)'}**\n"
            f"SteamID: **{steam_id}**"
        )
    else:
        msg = (
            f"Unban command sent, but SteamID **{steam_id}** still appears in the ban list.\n"
            f"Player input was: **{player_input}**"
        )

    await interaction.followup.send(msg)


def format_message(banned_table: list, server: str) -> str:
    msg = f"""**{server} Bans:**
```
{tabulate(banned_table, headers=["Name", "SteamID"])}
```
"""
    return msg


@ban_group.command()
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def list(interaction: discord.Interaction):
    """Retrieve a list of all banned players across servers."""
    await interaction.response.defer()

    # We will build three inputs for our format_message function
    banned_lists = {server: [] for server in SYSTEM_USERS.values()}

    # Really what I should do is query with all the banned
    # usernames collected first, not make a call for each one in a loop
    for server in SYSTEM_USERS.values():

        servers_banned_players = await get_all_banned_players(server)
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
            user = await get_player_by_steamid(server, steamid)
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

    formatted_messages = []
    for category, server in SYSTEM_USERS.items():
        banned_list = [[p[0], p[1]] for p in banned_lists[server]]
        formatted_messages.append(format_message(banned_list, category))

    output = (
        "*If the players name is None then they were banned before ever joining.\n\n"
        + "".join(formatted_messages)
    )

    await interaction.followup.send(output)
