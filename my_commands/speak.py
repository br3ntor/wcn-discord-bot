import discord
from discord import app_commands

from config import Config

PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


@app_commands.command()
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def speak(
    interaction: discord.Interaction, channel: discord.TextChannel, message: str
):
    """Make the bot speak in a specific channel."""
    await channel.send(message)
    await interaction.response.send_message(
        f"Message sent to {channel.name}:\n>{message}", ephemeral=True
    )
