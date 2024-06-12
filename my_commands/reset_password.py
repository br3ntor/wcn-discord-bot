import discord
from discord import app_commands

from config import LOCAL_SERVER_NAMES
from utils.db_helpers import reset_user_password


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(LOCAL_SERVER_NAMES)
    ],
)
async def reset_password(
    interaction: discord.Interaction, server: app_commands.Choice[int], playername: str
):
    """Reset a players password."""
    attempted_reset_response = await reset_user_password(server.name, playername)
    await interaction.response.send_message(attempted_reset_response)
