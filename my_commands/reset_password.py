import discord
from discord import app_commands

from config import SERVER_NAMES
from utils.db_helpers import PasswordResetStatus, reset_player_password


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ],
)
@app_commands.describe(server="Which server?", playername="Which player?")
async def reset_password(
    interaction: discord.Interaction, server: app_commands.Choice[int], playername: str
):
    """Reset a players password."""
    system_user = SERVER_NAMES[server.name]
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
