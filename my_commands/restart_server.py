import asyncio
import os

import discord
from discord import app_commands

from config import REMOTE_SERVER_IP, SERVER_DATA
from utils.server_helpers import server_isrunning

MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", 0))
ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))

# I just want the servers with remote ip used in all commands but steam api calls since I can get home server with that easily too
ENABLED_SERVERS = [
    server["name"] for server in SERVER_DATA if server["ip"] in REMOTE_SERVER_IP
]


# TODO: Extend this class to also take an action_to_confirm to build that into the
# yes or no response message
# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("Restart confirmed.", ephemeral=True)
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except
    # sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Restart canceled.", ephemeral=True)
        self.value = False
        self.stop()


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(ENABLED_SERVERS)
    ]
)
async def restart_server(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts the server!!!"""

    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "WTF are you trying to do even?", ephemeral=True
        )
        return

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    # Send the question with buttons
    view = Confirm()
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
        print("Timed out...")
    elif view.value:
        print("Confirmed...")

        is_running = await server_isrunning(server.name)
        if not is_running:
            await interaction.followup.send(f"**{server.name}** is **NOT** running!")
            return

        initiated_by = (
            f"**{server.name}** restart "
            f"initiated by {interaction.user.display_name}..."
        )

        # Maybe this should be moved higher in the function but can do later or not
        assert isinstance(interaction.guild, discord.Guild)
        channel = interaction.guild.get_channel(ANNOUNCE_CHANNEL)
        assert isinstance(channel, discord.TextChannel)

        await channel.send(initiated_by)

        # Feedback for mod chanel
        await interaction.followup.send(initiated_by)

        try:
            cmd = [
                "systemctl",
                "restart",
                server.name,
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

            succeeded = (
                f"Success! The **{server.name}** was shut down "
                "and is now starting back up."
            )
            failed = "Something went wrong, maybe..."
            status = succeeded if process.returncode == 0 else failed

            # TODO: Figure out the logging module instead of printing
            print(process)

            # Announce restart
            await channel.send(status)
        except Exception as e:
            print(f"Subprocess error occurred: {e}")

    else:
        print("Cancelled...")
