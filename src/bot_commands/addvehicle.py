import re

import discord
from discord import app_commands

from src.config import Config
from src.services.pz_server import pz_addvehicle
from src.services.server import server_isrunning
from src.utils.helpers import make_player_autocomplete, make_vehicle_autocomplete

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
    player="The name of the player to spawn the vehicle near.",
    vehicle="The vehicle type in Module.Vehicle format (e.g., Base.VanAmbulance).",
)
@app_commands.autocomplete(player=make_player_autocomplete(), vehicle=make_vehicle_autocomplete())
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def addvehicle(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    player: str,
    vehicle: str,
):
    """Spawn a vehicle near a player."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed in player name.")
        return

    if re.search(r"[\"']", vehicle):
        await interaction.response.send_message("Quotes not allowed in vehicle name.")
        return

    await interaction.response.defer()

    system_user = SYSTEM_USERS[server.name]

    if not await server_isrunning(system_user):
        await interaction.followup.send(f"**{server.name}** is **NOT** running!")
        return

    success, response = await pz_addvehicle(system_user, player, vehicle)

    if success:
        await interaction.followup.send(
            f"Spawned **{vehicle}** near **{player}** on **{server.name}**."
        )
    else:
        await interaction.followup.send(
            f"Failed to spawn vehicle near **{player}**: {response}"
        )
