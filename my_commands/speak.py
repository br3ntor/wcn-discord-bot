import discord
from discord import app_commands

group = app_commands.Group(name="uwu", description="Lets try this!")


# @app_commands.command()
@group.command()
async def speak(interaction: discord.Interaction, message: str):
    """Make the bot speak."""
    await interaction.response.send_message(message)


@group.command()
async def say_poop(interaction: discord.Interaction):
    """A very important message."""
    await interaction.response.send_message("Poop")
