import discord
from discord import app_commands


@app_commands.command()
async def speak(
    interaction: discord.Interaction, channel: discord.TextChannel, message: str
):
    """Make the bot speak in a specific channel."""
    await channel.send(message)
    await interaction.response.send_message(message)
