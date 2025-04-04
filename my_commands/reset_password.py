import discord
from discord import app_commands

from config import Config
from lib.game_db import PasswordResetStatus, reset_player_password

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
    reset_response = await reset_player_password(system_user, playername)
    match reset_response:
        case PasswordResetStatus.USER_NOT_FOUND:
            response_msg = (
                f"**{playername}** not found on the **{server.name}** server."
            )
        case PasswordResetStatus.DB_FILE_NOT_FOUND:
            response_msg = f"db file not found on the **{server.name}** server."
        case PasswordResetStatus.DATABASE_ACCESS_ERROR:
            response_msg = f"Error accessing database on the **{server.name}** server."
        case PasswordResetStatus.UNKNOWN_ERROR:
            response_msg = "An unknown error has occurred, spooky!"
        case PasswordResetStatus.SUCCESS:
            response_msg = f"**{playername}**'s password has been reset on the **{server.name}** server. They may login with any new password."

    await interaction.response.send_message(response_msg)
