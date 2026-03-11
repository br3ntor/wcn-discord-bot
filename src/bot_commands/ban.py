import io
import logging
import re

import discord
from discord import app_commands
from tabulate import tabulate

from src.config import Config
from src.services.game_db import (
    get_all_banned_players,
    get_player,
    get_player_by_steamid,
)
from src.services.pz_server import pz_ban_player, pz_unban_player
from src.services.server import get_game_version, server_isrunning

logger = logging.getLogger(__name__)

ban_group = app_commands.Group(
    name="ban", description="Ban, unban, and list banned players."
)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
def is_valid_steam_id(steam_id: str) -> bool:
    return steam_id.isdigit() and len(steam_id) == 17


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
    game_version = get_game_version(system_user)
    steam_id = ""

    # Determine if input is a SteamID
    if player_input.isdigit():
        steam_id = player_input
        if not is_valid_steam_id(steam_id):
            await interaction.followup.send("SteamID must be exactly 17 digits.")
            return
        row = await get_player_by_steamid(system_user, steam_id)
        player_name = row[2] if row else None
    else:
        # Lookup player by name
        player_row = await get_player(system_user, player_input)

        # If player_row is a str then there must be something wrong and then I"m just sending
        # it as a discord message which is just lazy but I still haven't changed it.
        if isinstance(player_row, str):
            await interaction.followup.send(player_row)
            return
        if not player_row:
            await interaction.followup.send(
                f"No player found with name **{player_input}**."
            )
            return

        # print(player_row)
        if game_version == "B41":
            steam_id = player_row[11]
        elif game_version == "B42":
            steam_id = player_row[8]

        player_name = player_input

    # Check if the game server is running
    if not await server_isrunning(system_user):
        await interaction.followup.send(f"**{server.name}** is **NOT** running!")
        return

    success, response = await pz_ban_player(system_user, steam_id)

    if success:
        msg = (
            f"Player has been **banned** from the **{server.name}** server.\n"
            f"Username: **{player_name or '(unknown)'}**\n"
            f"SteamID: **{steam_id}**"
        )
    else:
        msg = f"Ban failed for SteamID **{steam_id}**: {response}"

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
    game_version = get_game_version(system_user)
    steam_id = ""

    # Determine if input is a SteamID
    if player_input.isdigit():
        steam_id = player_input
        if not is_valid_steam_id(steam_id):
            await interaction.followup.send("SteamID must be exactly 17 digits.")
            return
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

        if game_version == "B41":
            steam_id = player_row[11]
        elif game_version == "B42":
            steam_id = player_row[8]

        player_name = player_input

    success, response = await pz_unban_player(system_user, steam_id)

    if success:
        msg = (
            f"Player has been **unbanned** from the **{server.name}** server.\n"
            f"Username: **{player_name or '(unknown)'}**\n"
            f"SteamID: **{steam_id}**"
        )
    else:
        msg = f"Unban failed for SteamID **{steam_id}**: {response}"

    await interaction.followup.send(msg)


# Updated format_message without markdown
def format_message(banned_table: list, server: str) -> str:
    msg = f"{server} Bans:\n{tabulate(banned_table, headers=['Name', 'SteamID'])}"
    return msg


@ban_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(
    server="Which server?",
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def list(interaction: discord.Interaction, server: app_commands.Choice[int]):
    """Retrieve a list of all banned players on the selected server."""
    await interaction.response.defer()
    system_user = SYSTEM_USERS[server.name]

    servers_banned_players = await get_all_banned_players(system_user)

    if not servers_banned_players:
        await interaction.followup.send("No banned players on this server.")
        return

    banned_players = []
    seen_players = []
    for b_player in servers_banned_players:
        steamid = b_player[0]

        if steamid in seen_players:
            continue

        seen_players.append(steamid)

        user = await get_player_by_steamid(system_user, steamid)
        if not user:
            banned_players.append(("None", steamid))
            continue
        elif isinstance(user, str):
            continue

        banned_players.append((user[2], steamid))

    category = next(k for k, v in SYSTEM_USERS.items() if v == system_user)

    banned_list = [[p[0], p[1]] for p in banned_players]
    msg = format_message(banned_list, category)

    note = "If the players name is None then they were banned before ever joining.\n\n"

    if not msg:
        await interaction.followup.send("No banned players on this server.")
        return

    content = note + msg
    file = discord.File(io.BytesIO(content.encode()), filename=f"banned_{category}.txt")
    await interaction.followup.send(f"Banned list for {category}:", file=file)
