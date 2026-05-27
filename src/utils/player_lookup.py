"""Shared player lookup utilities for resolving names to Steam IDs."""

import re
from typing import Optional, Tuple

from src.config import Config
from src.services.game_db import gamedb_get_player_by_name, gamedb_get_player_by_steamid
from src.services.server import get_game_version

SYSTEM_USERS = Config.SYSTEM_USERS


def is_valid_steam_id(steam_id: str) -> bool:
    """Check if a string is a valid 17-digit Steam ID."""
    return steam_id.isdigit() and len(steam_id) == 17


def has_invalid_quotes(text: str) -> bool:
    """Check if text contains quotes which could cause issues."""
    return bool(re.search(r'["\']', text))


async def lookup_player(
    system_user: str, player_input: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Look up a player by name or SteamID.

    Returns:
        Tuple of (steam_id, player_name, error_message)
        - steam_id: The player's Steam ID if found, None otherwise
        - player_name: The player's name if found, None otherwise
        - error_message: Error message if lookup failed, None otherwise
    """
    if has_invalid_quotes(player_input):
        return None, None, "Quotes are not allowed."

    game_version = get_game_version(system_user)
    steam_id = ""
    player_name = None

    # Determine if input is a SteamID
    if player_input.isdigit():
        steam_id = player_input
        if not is_valid_steam_id(steam_id):
            return None, None, "SteamID must be exactly 17 digits."
        row = await gamedb_get_player_by_steamid(system_user, steam_id)
        player_name = row[2] if row else None
    else:
        # Lookup player by name
        player_row = await gamedb_get_player_by_name(system_user, player_input)

        # If player_row is a str then there must be something wrong
        if isinstance(player_row, str):
            return None, None, player_row
        if not player_row:
            return None, None, f"No player found with name **{player_input}**."

        if game_version == "B41":
            steam_id = player_row[11]
        elif game_version == "B42":
            steam_id = player_row[8]

        player_name = player_input

    return steam_id, player_name, None


async def resolve_steam_id(player_input: str) -> Tuple[Optional[str], bool]:
    """
    Try to resolve a player input to a Steam ID by checking all servers.

    Returns:
        Tuple of (steam_id, was_resolved)
    """
    if is_valid_steam_id(player_input):
        return player_input, True

    # Try to find the player on any server
    for system_user in SYSTEM_USERS.values():
        player_row = await gamedb_get_player_by_name(system_user, player_input)
        if isinstance(player_row, str) or not player_row:
            continue

        game_version = get_game_version(system_user)
        if game_version == "B41":
            return player_row[11], True
        elif game_version == "B42":
            return player_row[8], True

    return None, False
