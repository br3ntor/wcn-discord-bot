import logging

import discord
from discord import app_commands

from src.config import Config
from src.services.server import restart_zomboid_server, server_isrunning
from src.services.server_monitor import start_restart_monitor
from src.utils.views import Confirm

logger = logging.getLogger(__name__)

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


@app_commands.command(name="now")
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(server="Which server?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def restart_server(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts a server immediately."""

    # Send the question with buttons
    view = Confirm(confirm_msg="Restart confirmed.", cancel_msg="Restart canceled.")
    await interaction.response.send_message(
        f"Restart the **{server.name}** server?", view=view, ephemeral=True
    )
    await view.wait()

    # Disable buttons after click
    for button in view.children:
        if isinstance(button, discord.ui.Button):
            button.disabled = True
    await interaction.edit_original_response(view=view)

    # Action taken based on interaction results
    if view.value is None:
        logger.info("Timed out...")
    elif view.value:
        logger.info("Restart Confirmed...")

        system_user = SYSTEM_USERS[server.name]

        is_running = await server_isrunning(system_user)
        if not is_running:
            await interaction.followup.send(
                f"**{server.name}** is **NOT** running!", ephemeral=True
            )
            return

        initiated_by = (
            f"**{server.name}** server restart "
            f"initiated by {interaction.user.display_name}..."
        )

        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        announce_chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL)

        if not isinstance(announce_chan, discord.TextChannel):
            await interaction.followup.send(
                "Announce channel is not a TextChanel.", ephemeral=True
            )
            return

        # Acknowledge in the channel the command was issued from
        await interaction.followup.send(
            f"**{server.name}** restart initiated — "
            f"announcement sent to <#{ANNOUNCE_CHANNEL}>."
        )

        # Let the people know whats up!
        await announce_chan.send(initiated_by)

        await restart_zomboid_server(system_user)

        status_msg = (
            f"Success! The **{server.name}** was shut down "
            "and is now starting back up."
        )

        # Announce restart
        await announce_chan.send(status_msg)

        start_restart_monitor(system_user, server.name, announce_chan)

    else:
        logger.info("Restart cancelled for %s...", server.name)
