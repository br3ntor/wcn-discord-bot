import asyncio
import datetime
import os

import discord
from discord import app_commands

MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID"))
ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL"))

last_run = datetime.datetime(1990, 1, 1)


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
async def restart_server(interaction: discord.Interaction):
    """Restarts the server!!!"""

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    # Place a rate limit on the command
    # TODO: Try the cooldown decorator
    # https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.checks.cooldown
    global last_run
    elapsed_time = datetime.datetime.now() - last_run
    if elapsed_time.seconds < 300:
        await interaction.response.send_message(
            f"Please wait {300 - elapsed_time.seconds} more seconds.", ephemeral=True
        )
        return

    # Send the question with buttons
    view = Confirm()
    await interaction.response.send_message(
        "Restart the server?", view=view, ephemeral=True
    )
    await view.wait()

    # Disable buttons after click
    for button in view.children:
        button.disabled = True
    await interaction.edit_original_response(view=view)

    # Action taken based on interaction results
    if view.value is None:
        print("Timed out...")
    elif view.value:
        print("Confirmed...")

        # Call the restart command, assuming server is running.
        # If it's not running, command will prompt for yes or no to start server.
        # I am ignoring this unil I learn more how to deal with that.
        initiated_by = (
            "Server restart " f"initiated by {interaction.user.display_name}..."
        )
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(initiated_by)

        # Feedback for mod chanel
        await interaction.followup.send(initiated_by)

        # Update last run time of command
        last_run = datetime.datetime.now()

        try:
            cmd = [
                "/home/pzserver/pzserver",
                "restart",
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

            succeeded = (
                "Success! The zomboid server was shut down "
                "and is now starting back up."
            )
            failed = "Something went wrong, maybe..."
            status = succeeded if process.returncode == 0 else failed

            # TODO: Figure out the logging module instead of printing
            print(process)

            # Announce restart
            await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(status)
        except asyncio.SubprocessError as e:
            print(f"Subprocess error occurred: {e}")

    else:
        print("Cancelled...")
