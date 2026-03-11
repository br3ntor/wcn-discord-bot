import discord
from discord import app_commands

from src.config import Config
from src.services.pz_server import pz_teleport_player

SYSTEM_USERS = Config.SYSTEM_USERS

SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(
    server="Which server?",
    player1="Who to teleport?",
    player2="Teleport to who?"
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def teleport(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    player1: str,
    player2: str,
):
    """Teleport a player to another player."""
    await interaction.response.defer()
    result, message = await pz_teleport_player(
        SYSTEM_USERS[server.name], player1, player2
    )
    if result:
        await interaction.followup.send(
            f"Successfully teleported **{player1}** to **{player2}** on the **{server.name}** server!"
        )
    else:
        await interaction.followup.send(f"Teleport failed: {message}")
