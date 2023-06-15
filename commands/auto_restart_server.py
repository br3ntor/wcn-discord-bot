import os
import subprocess
import asyncio
from math import ceil
import discord
from discord import app_commands

ANNOUNCE_CHANNEL = int(os.getenv("SPAM_CHANNEL"))


COUNT_DOWN_TIME = 90  # seconds

# Track if countdown timer is running
light_count_down_started = False
heavy_count_down_started = False

# If this is ever true we will abort shutdown
abort_signal = False


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
async def under_construction(
    interaction: discord.Interaction,
):
    """Restarts server in 5min."""
    global light_count_down_started, heavy_count_down_started, abort_signal

    # This coveres both, I think...
    abort_signal = False

    # Create the view containing our dropdown
    view = RestartServerView()

    await interaction.response.send_message(
        "So you want to restart the...", view=view, ephemeral=False
    )
    await view.wait()

    # Still not sure if this should be at the end of select_channels...
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
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(init_msg)

        # Start tracking
        if view.server == "light":
            light_count_down_started = True
        elif view.server == "heavy":
            heavy_count_down_started = True

        # start_time = time.time()
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + COUNT_DOWN_TIME  # 5 minutes = 300 seconds

        while asyncio.get_event_loop().time() < end_time:
            if abort_signal == True:
                await interaction.channel.send("Auto restart ABORTED 👼")
                return await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(
                    "Auto restart ABORTED 👼"
                )

            seconds_left = ceil(
                COUNT_DOWN_TIME - (asyncio.get_event_loop().time() - start_time)
            )

            # At the 1 minute mark
            if seconds_left == 60:
                await interaction.channel.send(
                    f"The {emoji}**{view.server.upper()}** server will restart in {seconds_left} seconds (Not really though)"
                )

            # Send command every n seconds if seconds are less than b
            if seconds_left % 5 == 0 and seconds_left <= 15:
                await interaction.channel.send(
                    f"The {emoji}**{view.server.upper()}** server will restart in {seconds_left} seconds (Not really though)"
                )
            # time.sleep(5)  # Pause for n seconds
            await asyncio.sleep(5)

        # Countdown is over so lets reset count_down trackers
        if view.server == "light":
            light_count_down_started = False
        elif view.server == "heavy":
            heavy_count_down_started = False

        # And finally I think we can call the command, but dont forget to make async
        # https://chat.openai.com/share/718cf2d0-65b6-44f4-9d27-8868c25a6071

        # cmd = ["systemctl", "restart", f"pzserver{view.server}"]
        # response = subprocess.run(cmd)

        restart_msg = f"The {emoji}**{view.server.upper()}** server will restart in **NOW**! (FAKE MSG)"
        await interaction.followup.send(restart_msg)
        await interaction.guild.get_channel(ANNOUNCE_CHANNEL).send(restart_msg)
    else:
        print("Cancelled...")


# @app_commands.choices(
#     server=[
#         app_commands.Choice(name="Light", value=1),
#         app_commands.Choice(name="Heavy", value=2),
#         app_commands.Choice(name="Both", value=3),
#     ]
# )
@app_commands.command()
async def canel_auto_restart(interaction: discord.Interaction):
    """ZOMG CANCEL B4 IT TOO LATE!!!."""
    global abort_signal
    abort_signal = True
    await interaction.response.send_message("Abort signal sent!")
