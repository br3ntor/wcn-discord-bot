import discord
from discord import app_commands

from src.config import Config

SERVER_DATA = Config.SERVER_DATA
SERVER_NAMES = Config.SERVER_NAMES


@app_commands.command(
    name="playerlist", description="Get a link to the current player list"
)
@app_commands.choices(
    server=[
        app_commands.Choice(name=name, value=name) for name in SERVER_NAMES.values()
    ]
)
@app_commands.describe(server="Which server?")
async def get_playerlist(
    interaction: discord.Interaction,
    server: app_commands.Choice[str],
):
    """Show a jump link to the player list message in the server's dedicated thread."""
    await interaction.response.defer()

    server_name = server.value

    # Find server config
    srv_info = next(
        (srv for srv in SERVER_DATA if srv["server_name"] == server_name), None
    )

    if srv_info is None:
        print(f"[Playerlist] No config found for server: {server_name}")
        await interaction.followup.send(
            "Couldn't find the player list for that server right now.", ephemeral=True
        )
        return

    # Safely get discord IDs
    discord_playerlist = srv_info.get("discord_playerlist") or {}
    thread_id = discord_playerlist.get("thread_id")
    message_id = discord_playerlist.get("message_id")

    if not thread_id or not message_id:
        print(f"[Playerlist] Missing thread_id or message_id for server: {server_name}")
        await interaction.followup.send(
            "The player list isn't set up for that server yet.", ephemeral=True
        )
        return

    guild = interaction.guild
    if not isinstance(guild, discord.Guild):
        print("[Playerlist] Command used outside a guild")
        await interaction.followup.send(
            "This command only works in a server.", ephemeral=True
        )
        return

    # Get thread from cache
    thread = guild.get_thread(thread_id)
    if not thread or not isinstance(thread, discord.Thread):
        print(
            f"[Playerlist] Could not find thread {thread_id} for server: {server_name}"
        )
        await interaction.followup.send(
            "Couldn't locate the player list thread right now.", ephemeral=True
        )
        return

    # Fetch the pinned/important message
    try:
        message = await thread.fetch_message(message_id)
    except discord.NotFound:
        print(
            f"[Playerlist] Message {message_id} not found in thread {thread_id} (server: {server_name})"
        )
        await interaction.followup.send(
            "The player list message seems to have been deleted.", ephemeral=True
        )
        return
    except discord.Forbidden:
        print(
            f"[Playerlist] No permission to read message {message_id} in thread {thread_id}"
        )
        await interaction.followup.send(
            "I don't have permission to view the player list.", ephemeral=True
        )
        return
    except Exception as e:
        print(f"[Playerlist] Unexpected error fetching message {message_id}: {e}")
        await interaction.followup.send(
            "Something went wrong while fetching the player list.", ephemeral=True
        )
        return

    # Success!
    await interaction.followup.send(
        f"Here's the current player list for **{server_name}**:\n{message.jump_url}"
    )
