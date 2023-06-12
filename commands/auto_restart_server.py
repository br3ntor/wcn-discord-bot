import time
import discord
from discord import app_commands

# Track if countdown timer is running
light_count_down_started = False
heavy_count_down_started = False


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ]
)
async def auto_restart_server(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
):
    """Restarts server in 5min."""
    global light_count_down_started, heavy_count_down_started

    destination_server = server.name.lower()

    await interaction.response.send_message(
        f"Starting countdown to restart the **{server.name}** server..."
    )

    # await interaction.response.defer()

    # Start tracking
    if destination_server == "light":
        light_count_down_started = True
    elif destination_server == "heavy":
        heavy_count_down_started = True

    start_time = time.time()
    countdown_seconds = 10
    end_time = start_time + countdown_seconds  # 5 minutes = 300 seconds

    while time.time() < end_time:
        seconds_left = countdown_seconds - (end_time - start_time)
        await interaction.channel.send(
            f"The **{server.name}** will restart in {seconds_left} (Not really though)"
        )
        time.sleep(1)  # Pause for 0.

    # Countdown is over so lets reset count_down trackers
    if destination_server == "light":
        light_count_down_started = False
    elif destination_server == "heavy":
        heavy_count_down_started = False

    await interaction.followup.send(
        f"Sup, it has been {round(end_time - start_time)} seconds."
    )


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
