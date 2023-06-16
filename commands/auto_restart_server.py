import os
import asyncio
from math import ceil
import discord
from discord import app_commands

ANNOUNCE_CHANNEL = int(os.getenv("SPAM_CHANNEL"))


COUNT_DOWN_TIME = 90  # seconds

# Track if countdown timer is running
countdown_isrunning = {"light": False, "heavy": False}

# Will abort any restart function if a count_down_started is True
abort_signal = False


async def send_server_msg(server, message):
    server_msg = "'servermsg \"" + message + "\"'"
    cmd = [
        "runuser",
        f"pzserver{server}",
        "-c",
        f"/home/pzserver{server}/pzserver send {server_msg}",
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )
    # Get the output of the subprocess.
    output, error = await process.communicate()
    print(output.decode())
    print(error.decode())


class RestartServerView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.server = None
        self.value = None

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Choose server...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="Light", description="The noob server", emoji="🥗"
            ),
            discord.SelectOption(
                label="Heavy", description="The pro server", emoji="🍖"
            ),
        ],
    )
    async def select_channels(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        # Enable buttons after channel select
        for element in self.children:
            if isinstance(element, discord.ui.Button):
                element.disabled = False
            if isinstance(element, discord.ui.Select):
                emoji = "🥗" if select.values[0].lower() == "light" else "🍖"
                element.placeholder = f"{emoji} {select.values[0]} Server"

        self.server = select.values[0].lower()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="Yes", style=discord.ButtonStyle.green, disabled=True, emoji="🔌"
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        server = "unknown"  # hehehe
        for element in self.children:
            if isinstance(element, discord.ui.Select):
                server = element.values[0]

        emoji = "🥗" if server.lower() == "light" else "🍖"
        msg = (
            f"Restart initiated for the {emoji}**{server.upper()}** server by "
            f"{interaction.user.display_name}, restarting in {COUNT_DOWN_TIME} seconds."
        )
        await interaction.response.send_message(msg)
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(
        label="No", style=discord.ButtonStyle.grey, disabled=False, emoji="🤡"
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"{interaction.user.display_name} changed their mind."
        )
        self.value = False
        self.stop()


@app_commands.command()
async def auto_server_restart(
    interaction: discord.Interaction,
):
    """Restarts server in 5min."""
    global abort_signal, countdown_isrunning

    abort_signal = False

    # Create the view containing our dropdown and buttons
    view = RestartServerView()

    await interaction.response.send_message(
        "So you want to restart the...", view=view, ephemeral=False
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
        emoji = "🥗" if view.server == "light" else "🍖"
        init_msg = (
            f"Restart initiated for the {emoji}**{view.server.upper()}** "
            f"server, restarting in {COUNT_DOWN_TIME} seconds. (JUST KIDDING)"
        )

        # Send players on server first restart warning
        await send_server_msg(
            view.server, f"Server will restart in {COUNT_DOWN_TIME} seconds."
        )

        # Send message to discord members announcing restart
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(init_msg)

        # Start tracking
        countdown_isrunning[view.server] = True

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + COUNT_DOWN_TIME

        while asyncio.get_event_loop().time() < end_time:
            if abort_signal == True:
                countdown_isrunning[view.server] = False
                await interaction.channel.send(
                    f"Auto restart ABORTED 👼 for the {emoji}**{view.server}** server."
                )
                return await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(
                    f"Auto restart ABORTED 👼 for the {emoji}**{view.server}** server."
                )

            seconds_left = ceil(
                COUNT_DOWN_TIME - (asyncio.get_event_loop().time() - start_time)
            )

            # At the 1 minute mark
            if seconds_left == 60:
                await send_server_msg(
                    view.server, f"The server will restart in {seconds_left} seconds!"
                )
                await interaction.channel.send(
                    f"The {emoji}**{view.server.upper()}** server will restart in {seconds_left} seconds (Not really though)"
                )
                await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(
                    f"The {emoji}**{view.server.upper()}** server will restart in {seconds_left} seconds (Not really though)"
                )

            # Send command every n seconds if seconds are less than b
            # if seconds_left % 5 == 0 and seconds_left <= 15:
            if seconds_left <= 15:
                await interaction.channel.send(
                    f"The {emoji}**{view.server.upper()}** server will restart in {seconds_left} seconds (Not really though)"
                )

            await asyncio.sleep(5)

        # Countdown is over so lets reset count_down trackers
        countdown_isrunning[view.server] = False

        try:
            cmd = ["systemctl", "restart", f"pzserver{view.server}"]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

            restart_msg = (
                f"Success! The {emoji}**{view.server.upper()}** server "
                "was restarted and is now loading back up."
            )
            await interaction.followup.send(restart_msg)
            await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(restart_msg)
        except asyncio.SubprocessError as e:
            print(f"Subprocess error occurred: {e}")

    else:
        print("Cancelled...")


@app_commands.command()
async def canel_auto_restart(interaction: discord.Interaction):
    """ZOMG CANCEL B4 IT TOO LATE!!!."""
    global abort_signal

    if countdown_isrunning["light"] or countdown_isrunning["heavy"]:
        abort_signal = True
        await interaction.response.send_message("Abort signal sent!")
    else:
        await interaction.response.send_message(
            "There is no countdown happening, this is you 🤡"
        )
