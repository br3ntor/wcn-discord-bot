import logging
import secrets
import string
from datetime import datetime

import discord
from discord import app_commands

from src.config import Config
from src.services.player_cache import PlayerCache

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES

_player_cache = PlayerCache()


def get_last_14th() -> datetime:
    """Get the date of the most recent 14th (either current month or previous month)."""
    today = datetime.now()

    if today.day < 14:
        if today.month == 1:
            return datetime(today.year - 1, 12, 14)
        else:
            return datetime(today.year, today.month - 1, 14)
    else:
        return datetime(today.year, today.month, 14)


def get_last_occurrence_of_day(day_number: int) -> datetime:
    """
    Get the date of the most recent occurrence of a specific day of the month.

    Args:
        day_number: The day of the month (e.g., 14 for the 14th) you want to find.

    Returns:
        A datetime object representing the most recent occurrence of that day.
    """
    if not 1 <= day_number <= 31:
        raise ValueError("day_number must be between 1 and 31.")

    today = datetime.now()

    if today.day < day_number:
        if today.month == 1:
            return datetime(today.year - 1, 12, day_number)
        else:
            return datetime(today.year, today.month - 1, day_number)
    else:
        return datetime(today.year, today.month, day_number)


def show_donation_progress(current_amount, goal_amount):
    """Prints a nice progress meter."""
    percentage = (current_amount / goal_amount) * 100
    percentage = round(percentage, 1)

    bar_length = 20
    filled_length = int(bar_length * min(percentage, 100) / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    message = f"Donation Progress: [{bar}] {percentage}%\n"
    message += f"We are {percentage}% towards our goal of ${goal_amount}!\n"
    message += f"Current amount raised: ${current_amount:.2f}"

    if percentage == 100:
        message += "\n🎉 Congratulations! We've met our donation goal! 🎉"
    elif percentage > 100:
        message += "\n🎉 Congratulations! We've met and exceeded our donation goal! 🎉"

    return message


def generate_pz_password(length: int = 12) -> str:
    """Generates a random alphanumeric password without symbols."""
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password


def make_player_autocomplete():
    """Creates an autocomplete callback for player name parameters."""

    async def autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        server_choice = getattr(interaction.namespace, "server", None)
        if not server_choice:
            return []

        # server_choice is the int value (1, 2, 3...) from app_commands.Choice
        # Map it back to server_name then system_user
        server_names = list(SERVER_NAMES.values())
        if server_choice < 1 or server_choice > len(server_names):
            return []

        server_name = server_names[server_choice - 1]
        system_user = SYSTEM_USERS.get(server_name)
        if not system_user:
            return []

        players = await _player_cache.get_players(system_user)
        if not players:
            return []

        players.sort(key=str.lower)

        if not current:
            return [app_commands.Choice(name=p, value=p) for p in players[:25]]

        matching = [p for p in players if current.lower() in p.lower()]
        return [app_commands.Choice(name=p, value=p) for p in matching[:25]]

    return autocomplete
