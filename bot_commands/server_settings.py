import os
import re
import tempfile

import discord
from discord import app_commands

from config import Config

PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
PZ_SERVER_INI_PATH = Config.SETTINGS_PATH
PUBLIC_KEYS = [
    "PVP",
    "SpawnItems",
    "PublicName",
    "PublicDescription",
    "MaxPlayers",
    "HoursForLootRespawn",
    "ConstructionPreventsLootRespawn",
    "NoFire",
    "MinutesPerPage",
    "SafeHouseRemovalTime",
    "SledgehammerOnlyInSafehouse",
    "SpeedLimit",
    "TrashDeleteAll",
    "CarEngineAttractionModifier",
]
REDACTED_KEYS = ["DiscordToken"]


@app_commands.command()
@app_commands.describe(full_settings="Show all settings (Admin only)")
@app_commands.guild_only()
async def server_settings(
    interaction: discord.Interaction, full_settings: bool = False
):
    """Display game server settings from pzserver.ini."""
    if PZ_SERVER_INI_PATH is None:
        await interaction.response.send_message(
            "Error: Server settings path not configured.", ephemeral=True
        )
        return

    settings = {}
    try:
        with open(PZ_SERVER_INI_PATH, "r") as file:
            for line in file:
                if line.strip() and not line.startswith("#"):
                    match = re.match(r"(\w+)=(.*)", line.strip())
                    if match:
                        key, value = match.groups()
                        settings[key] = value

        # Cast user to Member and check admin role
        member = interaction.user
        is_admin = isinstance(member, discord.Member) and any(
            role.id == PZ_ADMIN_ROLE_ID for role in member.roles
        )

        # Filter settings based on user role, full_settings, and redacted keys
        display_settings = {}
        if is_admin and full_settings:
            display_settings = {
                k: v for k, v in settings.items() if k not in REDACTED_KEYS
            }
        else:
            display_settings = {k: v for k, v in settings.items() if k in PUBLIC_KEYS}

        # Non-admins or admins without full_settings: send as code block
        if not (is_admin and full_settings):
            settings_text = "\n\n".join(
                f"{key}: {value or 'None'}" for key, value in display_settings.items()
            )
            await interaction.response.send_message(
                f"```Zomboid Server Settings\n=======================\n\n{settings_text}\n```"
            )
            return

        # Admins with full_settings: send as text file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("Zomboid Server Settings\n")
            temp_file.write("=======================\n\n")
            for key, value in display_settings.items():
                temp_file.write(f"{key}: {value or 'None'}\n\n")
            temp_file_path = temp_file.name

        await interaction.response.send_message(
            content="Zomboid server settings (except redacted):",
            file=discord.File(temp_file_path),
            ephemeral=True,
        )

        # Clean up
        os.remove(temp_file_path)

    except FileNotFoundError:
        await interaction.response.send_message(
            f"Error: {PZ_SERVER_INI_PATH} not found.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Error reading settings: {str(e)}", ephemeral=True
        )
