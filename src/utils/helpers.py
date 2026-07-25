import logging
import secrets
import string
from datetime import datetime

import discord
from discord import app_commands

from src.config import Config
from src.services.item_cache import item_cache
from src.services.player_cache import PlayerCache
from src.services.vehicle_cache import vehicle_cache

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


def format_remaining(until: datetime, now: datetime) -> str:
    """Format the duration between *until* and *now* as a human-readable string."""
    seconds = max(1, int((until - now).total_seconds()))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts)


def format_player_stats(stats: dict, player_name: str) -> str:
    """Format a player command-count stats dict into a display string."""
    char_counts = stats.get(player_name, {})
    if not char_counts:
        return ""

    heals_admin = char_counts.get("heal_player", 0)
    heals_self = char_counts.get("heal_self", 0)
    restores_admin = char_counts.get("restore_levels", 0)
    restores_self = char_counts.get("restore_self", 0)
    heals_total = heals_admin + heals_self
    restores_total = restores_admin + restores_self

    parts = [f"**{player_name}**:"]
    parts.append(
        f"{heals_total} heal{'s' if heals_total != 1 else ''}"
        f" ({heals_admin} admin, {heals_self} self)"
    )
    parts.append(
        f"{restores_total} restore{'s' if restores_total != 1 else ''}"
        f" ({restores_admin} admin, {restores_self} self)"
    )
    return "\n" + "  ".join(parts)


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


def make_item_autocomplete():
    """Creates an autocomplete callback for item parameters."""

    async def autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        server_choice = getattr(interaction.namespace, "server", None)
        if not server_choice:
            return []

        server_names = list(SERVER_NAMES.values())
        if server_choice < 1 or server_choice > len(server_names):
            return []

        server_name = server_names[server_choice - 1]
        system_user = SYSTEM_USERS.get(server_name)
        if not system_user:
            return []

        items = item_cache.get_items(system_user)
        if not items:
            return []

        if not current:
            choices = []
            for item_id, display_name in items[:25]:
                label = _item_label(item_id, display_name)
                choices.append(app_commands.Choice(name=label, value=item_id))
            return choices

        current_lower = current.lower()
        matching = []
        for item_id, display_name in items:
            if current_lower in item_id.lower() or (
                display_name and current_lower in display_name.lower()
            ):
                matching.append((item_id, display_name))
            if len(matching) >= 25:
                break

        choices = []
        for item_id, display_name in matching[:25]:
            label = _item_label(item_id, display_name)
            choices.append(app_commands.Choice(name=label, value=item_id))
        return choices

    return autocomplete


def _item_label(item_id: str, display_name: str) -> str:
    if display_name:
        label = f"{item_id} - {display_name}"
    else:
        label = item_id
    if len(label) > 100:
        label = label[:97] + "..."
    return label


def make_vehicle_autocomplete():
    """Creates an autocomplete callback for vehicle parameters."""

    async def autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        server_choice = getattr(interaction.namespace, "server", None)
        if not server_choice:
            return []

        server_names = list(SERVER_NAMES.values())
        if server_choice < 1 or server_choice > len(server_names):
            return []

        server_name = server_names[server_choice - 1]
        system_user = SYSTEM_USERS.get(server_name)
        if not system_user:
            return []

        vehicles = vehicle_cache.get_vehicles(system_user)
        if not vehicles:
            return []

        if not current:
            choices = []
            for vehicle_id, display_name in vehicles[:25]:
                label = _item_label(vehicle_id, display_name)
                choices.append(app_commands.Choice(name=label, value=vehicle_id))
            return choices

        current_lower = current.lower()
        matching = []
        for vehicle_id, display_name in vehicles:
            if current_lower in vehicle_id.lower() or (
                display_name and current_lower in display_name.lower()
            ):
                matching.append((vehicle_id, display_name))
            if len(matching) >= 25:
                break

        choices = []
        for vehicle_id, display_name in matching[:25]:
            label = _item_label(vehicle_id, display_name)
            choices.append(app_commands.Choice(name=label, value=vehicle_id))
        return choices

    return autocomplete
