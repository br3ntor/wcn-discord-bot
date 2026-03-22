import discord
from discord import app_commands

from src.services.gist_updater import update_all_modlist_gists


@app_commands.command(name="mods_lists")
async def update_mods_lists(
    interaction: discord.Interaction,
):
    """Updates the list of mods for all server."""
    await interaction.response.defer()
    links = await update_all_modlist_gists()
    formatted_links = "\n".join(links)

    await interaction.followup.send(f"List of mods on the server(s)\n{formatted_links}")
