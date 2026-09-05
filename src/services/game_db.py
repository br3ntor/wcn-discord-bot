import logging
from typing import Optional

import aiosqlite

from src.services.server import get_game_db_path, get_game_version

logger = logging.getLogger(__name__)

# (username, role, steamid) — steamid may be None for pre-steam/local accounts
StaffRow = tuple[str, str, str | None]


def gamedb_check_db_exists(system_user: str) -> tuple[bool, str]:
    path = get_game_db_path(system_user)
    if not path.exists():
        error_message = f"File does not exist:\n{path}"
        logger.error(error_message)
        return False, f"File does not exist for {system_user} server"
    return True, str(path)


async def gamedb_get_player_by_name(
    system_user: str, username: str
) -> Optional[aiosqlite.Row] | str:
    """Return the db row for a player."""
    file_exists, result = gamedb_check_db_exists(system_user)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(str(get_game_db_path(system_user))) as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE username=?", [username]
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {system_user} server"


async def gamedb_get_player_by_steamid(system_user: str, steamid: str):
    """Return the db row for a player."""
    file_exists, result = gamedb_check_db_exists(system_user)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(str(get_game_db_path(system_user))) as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE steamid=?", [steamid]
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {system_user} server"


async def gamedb_get_players_by_steamid(system_user: str, steamid: str):
    """Return all whitelist rows for a steam ID."""
    file_exists, result = gamedb_check_db_exists(system_user)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(str(get_game_db_path(system_user))) as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE steamid=?", [steamid]
            ) as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {system_user} server"


async def gamedb_get_ban_by_steamid(system_user: str, steamid: str):
    """Return the db row for a banned player."""
    file_exists, result = gamedb_check_db_exists(system_user)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(str(get_game_db_path(system_user))) as db:
            async with db.execute(
                "SELECT * FROM bannedid WHERE steamid=?", [steamid]
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {system_user} server"


async def gamedb_get_all_bans(system_user: str):
    """Return all banned users on a server."""
    file_exists, result = gamedb_check_db_exists(system_user)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(str(get_game_db_path(system_user))) as db:
            async with db.execute("SELECT * FROM bannedid") as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {system_user} server"


async def gamedb_get_staff(system_user: str) -> list[StaffRow] | str:
    """Return (username, role, steamid) rows for every elevated user."""
    file_exists, result = gamedb_check_db_exists(system_user)
    if not file_exists:
        return result

    game_version = get_game_version(system_user)
    try:
        async with aiosqlite.connect(str(get_game_db_path(system_user))) as db:
            if game_version == "B41":
                # accesslevel is already the human-readable role name;
                # blank/NULL means base 'regular user' and 'none' is a
                # demoted user, neither counts as staff
                query = """
                    SELECT username, accesslevel, steamid FROM whitelist
                    WHERE accesslevel IS NOT NULL AND accesslevel != ''
                    AND accesslevel != 'none'
                """
            else:
                # B42: whitelist.role is a numeric FK into the `role` table.
                # id 1 = banned, id 2 = user (base), id 3 = priority (login
                # queue priority, not staff). Anything > 3 is elevated.
                query = """
                    SELECT w.username, r.name, w.steamid
                    FROM whitelist w
                    JOIN role r ON w.role = r.id
                    WHERE r.id > 3
                """
            async with db.execute(query) as cursor:
                staff = [(row[0], row[1], row[2]) async for row in cursor]

        return staff

    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {system_user} server"
