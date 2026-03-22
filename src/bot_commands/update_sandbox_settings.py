import discord
from discord import app_commands

from src.services.gist_updater import update_all_sandbox_gists


@app_commands.command(name="sandbox_settings")
async def update_sandbox_settings(interaction: discord.Interaction):
    """Updates server sandbox settings gist."""
    await interaction.response.defer()
    links = await update_all_sandbox_gists()
    formatted_links = "\n".join(links)

    await interaction.followup.send(f"Sandbox settings:\n{formatted_links}")
