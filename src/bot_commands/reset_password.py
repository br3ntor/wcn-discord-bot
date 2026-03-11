import discord
from discord import app_commands

from src.config import Config
from src.services.game_db import get_player
from src.services.pz_server import pz_reset_password_b41, pz_setpassword_b42
from src.services.server import get_game_version, server_isrunning
from src.utils.helpers import generate_pz_password

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ],
)
@app_commands.describe(server="Which server?", playername="Which player?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def reset_password(
    interaction: discord.Interaction, server: app_commands.Choice[int], playername: str
):
    """Reset a players password."""
    system_user = SYSTEM_USERS[server.name]
    game_version = get_game_version(system_user)

    if game_version == "UNKNOWN":
        await interaction.response.send_message(
            f"Unable to determine game version for **{server.name}** server.",
            ephemeral=True,
        )
        return

    player_row = await get_player(system_user, playername)
    if isinstance(player_row, str):
        await interaction.response.send_message(player_row, ephemeral=True)
        return

    if not player_row:
        await interaction.response.send_message(
            f"**{playername}** not found on the **{server.name}** server.",
            ephemeral=True,
        )
        return

    if not await server_isrunning(system_user):
        await interaction.response.send_message(
            f"{server.name} is **NOT** running!", ephemeral=True
        )
        return

    if game_version == "B42":
        new_pass = generate_pz_password(12)
        success, response = await pz_setpassword_b42(system_user, playername, new_pass)
        if success:
            await interaction.response.send_message(
                f"The password for {playername} has been reset to: {new_pass}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(response, ephemeral=True)
        return

    new_pass = generate_pz_password(12)
    success, response = await pz_reset_password_b41(system_user, playername, new_pass)
    if success:
        await interaction.response.send_message(
            f"The password for {playername} has been reset to: {new_pass}",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(response, ephemeral=True)
