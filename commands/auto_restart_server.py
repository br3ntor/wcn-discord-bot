import re
import time
import discord
from discord import app_commands


COUNT_DOWN_TIME = 300  # 300 sec = 5min

# Track if countdown timer is running
light_count_down_started = False
heavy_count_down_started = False


class RestartServerView(discord.ui.View):
    def __init__(self):
        super().__init__()
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
                print("Enabling button...")
                element.disabled = False
            if isinstance(element, discord.ui.Select):
                emoji = "🥗" if select.values[0].lower() == "light" else "🍖"
                element.placeholder = f"{emoji} {select.values[0]} Server"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, disabled=True)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        server = "unknown"  # hehehe
        for element in self.children:
            if isinstance(element, discord.ui.Select):
                server = element.values[0]

        emoji = "🥗" if server.lower() == "light" else "🍖"
        msg = (
            f"Server restart initiated for the {emoji}**{server.upper()}** "
            f"server by {interaction.user.display_name}, restarting in {COUNT_DOWN_TIME} seconds."
        )
        await interaction.response.send_message(msg)
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.grey, disabled=False)
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
    global light_count_down_started, heavy_count_down_started

    # destination_server = server.name.lower()

    # Create the view containing our dropdown
    view = RestartServerView()

    await interaction.response.send_message(
        "So you want to restart the...", view=view, ephemeral=True
    )
    await view.wait()

    # Still not sure if this should be at the end of select_channels...
    for element in view.children:
        element.disabled = True
    await interaction.edit_original_response(view=view)

    # Start tracking
    # if destination_server == "light":
    #     light_count_down_started = True
    # elif destination_server == "heavy":
    #     heavy_count_down_started = True

    # start_time = time.time()
    # countdown_seconds = 10
    # end_time = start_time + countdown_seconds  # 5 minutes = 300 seconds

    # while time.time() < end_time:
    #     seconds_left = countdown_seconds - (end_time - start_time)
    #     await interaction.channel.send(
    #         f"The **{server.name}** will restart in {seconds_left} (Not really though)"
    #     )
    #     time.sleep(1)  # Pause for 0.

    # # Countdown is over so lets reset count_down trackers
    # if destination_server == "light":
    #     light_count_down_started = False
    # elif destination_server == "heavy":
    #     heavy_count_down_started = False

    # await interaction.followup.send(
    #     f"Sup, it has been {round(end_time - start_time)} seconds."
    # )


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
        app_commands.Choice(name="Both", value=3),
    ]
)
async def canel_auto_restart(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """ZOMG CANCEL B4 IT TOO LATE!!!."""
    await interaction.response.send_message(
        "Yousa wanna cancel the server restart, mesa tinkin?"
    )


# def execute_for_five_minutes():
#     start_time = time.time()
#     end_time = start_time + 300  # 5 minutes = 300 seconds

#     # Add a flag for cancellation
#     cancelled = False

#     while time.time() < end_time:
#         # Check for cancellation
#         if cancelled:
#             break

#         # Your code logic here
#         time.sleep(0.01)  # Pause for 0.01 seconds (adjust as needed)

#     if cancelled:
#         print("Execution cancelled.")
#     else:
#         print("Execution completed.")


# Usage example:
# execute_for_five_minutes()
