import discord
from discord import app_commands


@app_commands.command()
async def speak(interaction: discord.Interaction, message: str):
    """Make the bot speak."""
    await interaction.response.send_message(message)
