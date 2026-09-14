import asyncio
import logging

import discord
from discord import app_commands

from src.config import Config
from src.services.pz_server import pz_godmode, pz_players

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_NAMES = Config.SERVER_NAMES

SERVER_CHOICES = [
    app_commands.Choice(name=srv, value=index + 1)
    for index, srv in enumerate(SERVER_NAMES.values())
]

GODMODE_DELAY_SECONDS = 0.2

godmode_group = app_commands.Group(
    name="godmode", description="Commands to toggle godmode for online players."
)


async def _toggle_godmode_all(
    interaction: discord.Interaction, server: app_commands.Choice[int], enable: bool
) -> None:
    system_user = SYSTEM_USERS[server.name]

    players = await pz_players(system_user)
    if players is None:
        await interaction.followup.send(
            f"I could not fetch the online players on **{server.name}**."
        )
        return
    if not players:
        await interaction.followup.send(
            f"No players are online on the **{server.name}** server."
        )
        return

    succeeded: list[str] = []
    failed: list[str] = []
    for player in players:
        result, _ = await pz_godmode(system_user, player, enable)
        if result:
            succeeded.append(player)
        else:
            failed.append(player)
        await asyncio.sleep(GODMODE_DELAY_SECONDS)

    action = "enabled" if enable else "removed"
    if succeeded:
        message = (
            f"Godmode **{action}** for **{len(succeeded)}** player(s) on the "
            f"**{server.name}** server: {', '.join(succeeded)}"
        )
    else:
        message = (
            f"Failed to {action} godmode for **{len(failed)}** player(s) on the "
            f"**{server.name}** server."
        )

    if failed:
        message += f"\nFailed: {', '.join(failed)}"

    await interaction.followup.send(message)


@godmode_group.command(name="all")
@app_commands.choices(server=SERVER_CHOICES)
@app_commands.describe(server="Which server?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def give_all(interaction: discord.Interaction, server: app_commands.Choice[int]):
    """Give godmode to every player currently online."""
    await interaction.response.defer()
    await _toggle_godmode_all(interaction, server, True)


@godmode_group.command(name="remove-all")
@app_commands.choices(server=SERVER_CHOICES)
@app_commands.describe(server="Which server?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def remove_all(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Remove godmode from every player currently online."""
    await interaction.response.defer()
    await _toggle_godmode_all(interaction, server, False)
