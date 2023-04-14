import os
import subprocess
import datetime
import discord
from discord import app_commands


MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID"))
ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL"))


last_run_light = datetime.datetime(1990, 1, 1)
last_run_heavy = datetime.datetime(1990, 1, 1)

# TODO: Give each command it's own file


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

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Restart canceled.", ephemeral=True)
        self.value = False
        self.stop()


@app_commands.command()
async def parrot(interaction: discord.Interaction, message: str):
    """Make bot send message."""
    await interaction.response.send_message(message)


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ]
)
@app_commands.describe(
    server="Which server should revieve this message?",
    message="What would you like to say.",
)
async def send_message(
    interaction: discord.Interaction, server: app_commands.Choice[int], message: str
):
    """Send a message to everyone in the server."""

    # Only discord mods can use the command
    # This gets taken care of when setuping up bot but its nice to have still
    # Oh also the framwork has a special check function to do this already I should use
    if interaction.user.get_role(MOD_ROLE_ID) == None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    # Respond to request to tell the user to wait a moment
    # This def needs to be called before doing work that takes time,
    # but I wonder if it may as well be first line of the function?
    await interaction.response.defer()

    # Send command and respond to result
    server_msg = "'servermsg \"" + message + "\"'"
    destination_server = server.name.lower()
    cmd = [
        "runuser",
        f"pzserver{destination_server}",
        "-c",
        f"/home/pzserver{destination_server}/pzserver send {server_msg}",
    ]
    response = subprocess.run(cmd, capture_output=True)
    last_line = response.stdout.decode("utf-8").split("\r")[-1]
    status = (
        f"Sent to {destination_server} server:\n> {message}"
        if "OK" in last_line
        else "Something wrong maybe\n" + last_line
    )

    # TODO: Figure out the logging module instead of printing
    print(response)
    await interaction.followup.send(status)


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ]
)
async def restart_server(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts the server!!!"""

    # Only discord mods can use the command
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    destination_server = server.name.lower()

    # Place rate limit the command
    global last_run_light, last_run_heavy
    last_run = last_run_light if destination_server == "light" else last_run_heavy
    elapsed_time = datetime.datetime.now() - last_run
    if elapsed_time.seconds < 300:
        await interaction.response.send_message(
            f"Please wait {300 - elapsed_time.seconds} more seconds.", ephemeral=True
        )
        return

    # Send the question with buttons
    view = Confirm()
    await interaction.response.send_message(
        f"Restart {destination_server} server?", view=view, ephemeral=True
    )
    await view.wait()

    # Disable buttons after click
    for button in view.children:
        button.disabled = True
    original_message = await interaction.original_message()
    await original_message.edit(view=view)

    # Action taken based on interaction results
    if view.value is None:
        print("Timed out...")
    elif view.value:
        print("Confirmed...")

        # Call the restart command, assuming server is running.
        # If it's not running, command will prompt for yes or no to start server.
        # I am ignoring this unil I learn more how to deal with that.
        initiated_by = f"{destination_server.capitalize()} server restart initiated by {interaction.user.display_name}..."
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(initiated_by)

        # Update last run time of command
        if destination_server == "light":
            last_run_light = datetime.datetime.now()
        elif destination_server == "heavy":
            last_run_heavy = datetime.datetime.now()

        cmd = ["systemctl", "restart", f"pzserver{destination_server}"]
        response = subprocess.run(cmd)

        succeeded = f"Success! The **{destination_server}** server was shut down and is now starting back up."
        failed = "Something wrong maybe..."
        status = succeeded if response.returncode == 0 else failed

        # # TODO: Figure out the logging module instead of printing
        print(response)

        # Announce restart
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(status)
    else:
        print("Cancelled...")
