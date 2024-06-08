import asyncio
import os

import discord
from discord import app_commands

from config import LOCAL_SERVER_NAMES
from utils.server_helpers import server_isrunning

MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", 0))
ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))


# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("Restart confirmed.", ephemeral=True)
        self.value = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Restart canceled.", ephemeral=True)
        self.value = False
        self.stop()


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(LOCAL_SERVER_NAMES)
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
        raise TypeError("Not a member")

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    # Feels like if this is here I need to defer before but this shouldnt ever be more than 3 seconds
    is_running = await server_isrunning(server.name)
    if not is_running:
        await interaction.response.send_message(
            f"**{server.name}** is **NOT** running!", ephemeral=True
        )
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

        initiated_by = (
            f"**{server.name}** restart "
            f"initiated by {interaction.user.display_name}..."
        )

        # Maybe this should be moved higher in the function but can do later or not
        assert isinstance(interaction.guild, discord.Guild)
        announce_chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL)
        assert isinstance(announce_chan, discord.TextChannel)

        # Let the people know whats up!
        await announce_chan.send(initiated_by)

        # Feedback for mod chanel
        assert isinstance(interaction.channel, discord.TextChannel)
        await interaction.channel.send(initiated_by)

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
            status_msg = succeeded if process.returncode == 0 else failed

            # TODO: Figure out the logging module instead of printing
            print(process)

            # Announce restart
            await announce_chan.send(status_msg)

            # Feedback for mod channel
            await interaction.channel.send(status_msg)

        except Exception as e:
            print(f"Subprocess error occurred: {e}")

    else:
        print("Cancelled...")
