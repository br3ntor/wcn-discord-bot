import os
import asyncio
from math import ceil
import discord
from discord import app_commands

ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL"))


COUNT_DOWN_TIME = 300  # seconds

# Track if countdown timer is running
countdown_isrunning = False

# Will abort any restart function if a count_down_started is True
abort_signal = False


# TODO: Add try catch for proper error handeling, maybe return true or success message
async def send_server_msg(message):
    server_msg = f'servermsg "{message}"'
    cmd = [
        "runuser",
        "pzserver",
        "-c",
        f"/home/pzserver/pzserver send '{server_msg}'",
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )
    # Get the output of the subprocess.
    output, error = await process.communicate()
    print(output.decode())
    print(error.decode())


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
        await interaction.response.send_message(
            "Auto Restart Confirmed.", ephemeral=True
        )
        await interaction.channel.send(
            f"{interaction.user.display_name} has initiated the server auto restart. Restarting in 5min."
        )
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except
    # sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Auto Restart Aborted.", ephemeral=True)
        await interaction.channel.send(
            f"{interaction.user.display_name} has aborted the auto restart!"
        )
        self.value = False
        self.stop()


@app_commands.command()
async def restart_server_auto(
    interaction: discord.Interaction,
):
    """Restarts server in 5min."""
    global abort_signal, countdown_isrunning

    abort_signal = False

    # Create the view containing our dropdown and buttons
    view = Confirm()

    await interaction.response.send_message(
        "Automatically restart the server after 5min?", view=view, ephemeral=True
    )
    await view.wait()

    # Disable all elements after button is pressed
    for element in view.children:
        element.disabled = True
    await interaction.edit_original_response(view=view)

    if view.value is None:
        print("Timed out...")
    elif view.value:
        print("Confirmed...")

        # Announce to discord members restart will happen after some minutes
        init_msg = (
            f"Auto restart initiated by {interaction.user.display_name}. "
            f"Server will restart in {COUNT_DOWN_TIME//60} minutes."
        )

        # Send players on server first restart warning
        await send_server_msg(f"Server will restart in {COUNT_DOWN_TIME//60} minutes.")

        # Send message to discord members announcing restart
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(init_msg)

        # Start tracking
        countdown_isrunning = True
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + COUNT_DOWN_TIME
        ran_once = False

        while asyncio.get_event_loop().time() < end_time:
            if abort_signal:
                # TODO: Consider adding server message to
                # inform players of abort in game
                countdown_isrunning = False
                await interaction.channel.send(
                    "Auto restart ABORTED 👼 for the zomboid server."
                )
                return await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(
                    "Auto restart ABORTED 👼 for the zomboid server."
                )

            seconds_left = ceil(
                COUNT_DOWN_TIME - (asyncio.get_event_loop().time() - start_time)
            )

            # At the 1 minute mark
            # ran_once is because I can't be certain seconds_left will tick on 60
            if seconds_left <= 60 and ran_once is False:
                ran_once = True
                await send_server_msg(
                    f"The server will restart in {seconds_left} seconds!"
                )
                await interaction.channel.send(
                    f"The zomboid server will restart in {seconds_left} seconds."
                )

            await asyncio.sleep(5)

        # Countdown is over so lets reset count_down trackers
        countdown_isrunning = False

        try:
            cmd = ["systemctl", "restart", "pzserver"]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

            restart_msg = (
                "Success! The zomboid server "
                "was restarted and is now loading back up."
            )
            await interaction.followup.send(restart_msg)
            await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(restart_msg)
        except asyncio.SubprocessError as e:
            print(f"Subprocess error occurred: {e}")

    else:
        print("Cancelled...")


@app_commands.command()
async def cancel_auto_restart(interaction: discord.Interaction):
    """ZOMG CANCEL B4 IT TOO LATE!!!."""
    global abort_signal

    if countdown_isrunning:
        abort_signal = True
        await interaction.response.send_message("Abort signal sent!")
    else:
        await interaction.response.send_message(
            "There is no countdown happening, this is you 🤡"
        )
