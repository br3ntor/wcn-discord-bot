import logging
import secrets
import string
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from src.config import Config
from src.services.bot_db import get_total_donations_since
from src.services.game_db import StaffRow
from src.services.item_cache import item_cache
from src.services.player_cache import PlayerCache
from src.services.vehicle_cache import vehicle_cache

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES

PACIFIC = ZoneInfo("America/Los_Angeles")

KOFI_GOAL_URL = "https://ko-fi.com/westcoastnoobs/goal"

_player_cache = PlayerCache()


def start_of_month_utc(now: datetime | None = None) -> datetime:
    """Get the start of the current month (Pacific time) converted to UTC.

    Donation rows are stored in UTC, so month boundaries are computed in
    Pacific time to match how the goal is perceived, then converted.
    """
    if now is None:
        now = datetime.now(PACIFIC)
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(PACIFIC)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start.astimezone(timezone.utc)


def days_left_in_month(now: datetime | None = None) -> int:
    """Days remaining in the current month (Pacific time)."""
    if now is None:
        now = datetime.now(PACIFIC)
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(PACIFIC)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    return (next_month - now).days


async def get_monthly_donation_progress() -> tuple[float, float]:
    """Return (current_amount, goal_amount) for this month's donation goal."""
    total = await get_total_donations_since(start_of_month_utc())
    return total + Config.KOFI_STARTING_AMOUNT, Config.KOFI_DONATION_GOAL


def show_donation_progress(current_amount, goal_amount):
    """Prints a nice progress meter for the monthly donation goal."""
    percentage = (current_amount / goal_amount) * 100
    percentage = round(percentage, 1)

    bar_length = 20
    filled_length = int(bar_length * min(percentage, 100) / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    days = days_left_in_month()
    day_text = f"{days} day{'s' if days != 1 else ''} left"

    message = f"Donation Progress: [{bar}] {percentage}%\n"
    message += (
        f"We are {percentage}% towards our goal of ${goal_amount:g} "
        f"by the end of the month ({day_text})!"
    )

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


def group_staff_by_steamid(
    rows: list[StaffRow],
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Group staff rows (username, role, steamid) by SteamID.

    Returns ordered (steamid, accounts) pairs. Groups with multiple
    accounts come first, then sorted by SteamID. Rows without a SteamID
    become their own group keyed as "nosteam:<username>". Account names
    within a group are sorted case-insensitively.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for username, role, steamid in rows:
        key = steamid if steamid else f"nosteam:{username}"
        groups.setdefault(key, []).append((username, role))

    for accounts in groups.values():
        accounts.sort(key=lambda account: account[0].casefold())

    return sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))


def _format_staff_section(server_name: str, rows: list[StaffRow]) -> str:
    """Format one server's staff rows into a markdown block."""
    if not rows:
        return f"**{server_name}** — no privileged users"

    groups = group_staff_by_steamid(rows)
    lines = [
        f"**{server_name}** — {len(rows)} account"
        f"{'s' if len(rows) != 1 else ''} across {len(groups)} "
        f"SteamID{'s' if len(groups) != 1 else ''}"
    ]
    for steamid, accounts in groups:
        roles = {role for _, role in accounts}
        if len(roles) == 1:
            account_part = ", ".join(name for name, _ in accounts) + f" ({roles.pop()})"
        else:
            account_part = ", ".join(f"{name} ({role})" for name, role in accounts)

        if steamid.startswith("nosteam:"):
            lines.append(f"• {account_part} — no SteamID")
        else:
            url = f"https://steamcommunity.com/profiles/{steamid}"
            lines.append(f"• [{steamid}](<{url}>) — {account_part}")
    return "\n".join(lines)


def _split_oversized_section(section: str, limit: int = 2000) -> list[str]:
    """Split a section longer than *limit* by lines, repeating the header."""
    if len(section) <= limit:
        return [section]

    header, _, body = section.partition("\n")
    room = limit - len(header) - 1
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in body.split("\n"):
        for piece in [line[i : i + room] for i in range(0, len(line), room)] or [""]:
            if current and size + len(piece) + 1 > room:
                chunks.append(f"{header}\n" + "\n".join(current))
                current = []
                size = 0
            current.append(piece)
            size += len(piece) + 1
    if current:
        chunks.append(f"{header}\n" + "\n".join(current))
    return chunks


def format_staff_listing(
    staff_by_server: dict[str, list[StaffRow]],
    errors_by_server: dict[str, str],
) -> list[str]:
    """Format privileged users per server into Discord-sized messages.

    Accounts are grouped by SteamID with a profile link per group and
    failed servers noted with a warning line. Returns a list of messages
    each within Discord's 2000 character limit (normally just one).
    """
    if not any(staff_by_server.values()) and not errors_by_server:
        return ["No privileged users found on any server."]

    sections = [
        _format_staff_section(server_name, rows)
        for server_name, rows in staff_by_server.items()
    ]
    sections += [
        f"⚠️ **{server_name}**: {error}"
        for server_name, error in errors_by_server.items()
    ]

    combined = "\n\n".join(sections)
    if len(combined) <= 2000:
        return [combined]

    messages: list[str] = []
    current = ""
    for section in sections:
        for part in _split_oversized_section(section):
            if not current:
                current = part
            elif len(current) + 2 + len(part) <= 2000:
                current = f"{current}\n\n{part}"
            else:
                messages.append(current)
                current = part
    if current:
        messages.append(current)
    return messages


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
