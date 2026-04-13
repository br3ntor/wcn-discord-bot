import re

import discord
from discord import app_commands

from src.config import Config
from src.services.pz_server import pz_additem
from src.services.server import server_isrunning
from src.utils.helpers import make_item_autocomplete, make_player_autocomplete

SYSTEM_USERS = Config.SYSTEM_USERS
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_NAMES = Config.SERVER_NAMES


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(
    server="Which server?",
    player="The name of the player to give the item to.",
    item="The item type in Module.Item format (e.g., Base.Axe).",
    count="How many to give (optional, default 1).",
)
@app_commands.autocomplete(player=make_player_autocomplete(), item=make_item_autocomplete())
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def additem(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    player: str,
    item: str,
    count: app_commands.Range[int, 1] = 1,
):
    """Give an item to a player."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed in player name.")
        return

    if re.search(r"[\"']", item):
        await interaction.response.send_message("Quotes not allowed in item name.")
        return

    await interaction.response.defer()

    system_user = SYSTEM_USERS[server.name]

    if not await server_isrunning(system_user):
        await interaction.followup.send(f"**{server.name}** is **NOT** running!")
        return

    success, response = await pz_additem(system_user, player, item, count)

    if success:
        await interaction.followup.send(
            f"Gave **{count}x {item}** to **{player}** on **{server.name}**."
        )
    else:
        await interaction.followup.send(
            f"Failed to give item to **{player}**: {response}"
        )
