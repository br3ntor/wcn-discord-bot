import logging
import os
from typing import Optional

import aiosqlite

from src.services.server import get_game_version

logger = logging.getLogger(__name__)


def gamedb_check_db_exists(server: str) -> tuple[bool, str]:
    path = f"/home/{server}/Zomboid/db/pzserver.db"
    if not os.path.exists(path):
        error_message = f"File does not exist:\n{path}"
        logger.error(error_message)
        return False, f"File does not exist for {server} server"
    return True, path


async def gamedb_get_player_by_name(
    server: str, username: str
) -> Optional[aiosqlite.Row] | str:
    """Return the db row for a player."""
    file_exists, result = gamedb_check_db_exists(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE username=?", [username]
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def gamedb_get_player_by_steamid(server: str, steamid: str):
    """Return the db row for a player."""
    file_exists, result = gamedb_check_db_exists(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE steamid=?", [steamid]
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def gamedb_get_players_by_steamid(server: str, steamid: str):
    """Return all whitelist rows for a steam ID."""
    file_exists, result = gamedb_check_db_exists(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE steamid=?", [steamid]
            ) as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def gamedb_get_ban_by_steamid(server: str, steamid: str):
    """Return the db row for a banned player."""
    file_exists, result = gamedb_check_db_exists(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT * FROM bannedid WHERE steamid=?", [steamid]
            ) as cursor:
                return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def gamedb_get_all_bans(server: str):
    """Return all banned users on a server."""
    file_exists, result = gamedb_check_db_exists(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute("SELECT * FROM bannedid") as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def gamedb_get_staff(server: str) -> str:
    file_exists, result = gamedb_check_db_exists(server)
    if not file_exists:
        return result

    game_version = get_game_version(server)
    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            if game_version == "B41":
                # accesslevel is already the human-readable role name;
                # blank/NULL means base 'regular user'
                query = """
                    SELECT username, accesslevel FROM whitelist
                    WHERE accesslevel IS NOT NULL AND accesslevel != ''
                """
            else:
                # B42: whitelist.role is a numeric FK into the `role` table.
                # id 1 = banned, id 2 = user (base). Anything > 2 is elevated.
                # Bump to > 3 if you want to exclude 'priority' too.
                query = """
                    SELECT w.username, r.name
                    FROM whitelist w
                    JOIN role r ON w.role = r.id
                    WHERE r.id > 2
                """
            async with db.execute(query) as cursor:
                the_boys = [(row[0], row[1]) async for row in cursor]

        the_boys.sort(key=lambda pair: pair[0].casefold())
        return ", ".join(f"{name} ({role})" for name, role in the_boys)

    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"
