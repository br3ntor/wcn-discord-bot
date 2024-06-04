import asyncio
import os
from math import ceil

import discord
from discord import app_commands

from config import SERVERNAMES
from utils.server_helpers import server_isrunning

ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))


COUNT_DOWN_TIME = 300  # seconds

# Track if countdown timer is running
# TODO: Use SERVERNAMES to make is_running object to track all servers
# countdown_isrunning = False
countdown_isrunning = {server: False for server in SERVERNAMES}

# Will abort any restart function if a count_down_started is True
abort_signal = False


async def send_server_msg(server: str, message: str):
    server_msg = f'servermsg "{message}"'
    cmd = [
        "runuser",
        f"{server}",
        "-c",
        f"/home/{server}/pzserver send '{server_msg}'",
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )
        # Get the output of the subprocess.
        output, error = await process.communicate()
    except Exception as e:
        print("Error in try block:", e)

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
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVERNAMES)
    ]
)
async def restart_server_auto(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts server in 5min."""
    global abort_signal, countdown_isrunning

    abort_signal = False

    # Create the view containing our dropdown and buttons
    view = Confirm()

    await interaction.response.send_message(
        f"Automatically restart the **{server.name}** after 5min?",
        view=view,
        ephemeral=True,
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

        is_running = await server_isrunning(server.name)
        if not is_running:
            await interaction.followup.send(f"**{server.name}** is **NOT** running!")
            return

        # Announce to discord members restart will happen after some minutes
        init_msg = (
            f"Auto restart initiated by {interaction.user.display_name}. "
            f"**{server.name}** will restart in {COUNT_DOWN_TIME//60} minutes."
        )

        # Send message to discord members announcing restart
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(init_msg)

        # Send players on server first restart warning
        await send_server_msg(
            server.name,
            f"Server will restart in {COUNT_DOWN_TIME//60} minutes.",
        )

        # Start tracking
        countdown_isrunning[server.name] = True
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + COUNT_DOWN_TIME
        ran_once = False

        # I feel like this all might be easier if instead of accurate time
        # We could just subtract 5 every 5 seconds till zero, then I can
        # be confident about my conditionals
        while asyncio.get_event_loop().time() < end_time:
            if abort_signal:
                # TODO: Consider adding server message to
                # inform players of abort in game
                countdown_isrunning[server.name] = False
                await interaction.channel.send(
                    f"Auto restart ABORTED 👼 for the **{server.name}** server."
                )
                return await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(
                    f"Auto restart ABORTED 👼 for the **{server.name}** server."
                )

            seconds_left = ceil(
                COUNT_DOWN_TIME - (asyncio.get_event_loop().time() - start_time)
            )

            # At the 1 minute mark
            # ran_once is because I can't be certain seconds_left will tick on 60
            if seconds_left <= 60 and ran_once is False:
                ran_once = True
                await interaction.channel.send(
                    f"The {server.name} server will restart in {seconds_left} seconds."
                )

            if seconds_left % 60 == 0:
                await send_server_msg(
                    server.name, f"The server will restart in {seconds_left} seconds!"
                )

            await asyncio.sleep(5)

        # Countdown is over so lets reset count_down trackers
        countdown_isrunning[server.name] = False

        try:
            cmd = [
                "systemctl",
                "restart",
                server.name,
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

        except Exception as e:
            print(f"error occurred: {e}")

        restart_msg = (
            f"Success! The **{server.name}** server "
            "was restarted and is now loading back up."
        )
        await interaction.followup.send(restart_msg)
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(restart_msg)

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
