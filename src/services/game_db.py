import logging
import os
from typing import Optional

import aiosqlite

from src.services.server import get_game_version

logger = logging.getLogger(__name__)
def check_db_file(server: str) -> tuple[bool, str]:
    path = f"/home/{server}/Zomboid/db/pzserver.db"
    if not os.path.exists(path):
        error_message = f"File does not exist:\n{path}"
        logger.error(error_message)
        return False, f"File does not exist for {server} server"
    return True, path


async def get_player(server: str, username: str) -> Optional[aiosqlite.Row] | str:
    """Return the db row for a player."""
    file_exists, result = check_db_file(server)
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


async def get_player_by_steamid(server: str, steamid: str):
    """Return the db row for a player."""
    file_exists, result = check_db_file(server)
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


async def get_banned_player(server: str, steamid: str):
    """Return the db row for a banned player."""
    file_exists, result = check_db_file(server)
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


async def get_all_banned_players(server: str):
    """Return all banned users on a server."""
    file_exists, result = check_db_file(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute("SELECT * FROM bannedid") as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def get_admins(server: str) -> str:
    file_exists, result = check_db_file(server)
    if not file_exists:
        return result

    game_version = get_game_version(server)

    where_clause = "role='7'"

    if game_version == "B41":
        where_clause = "accesslevel='admin'"

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            query = f"SELECT username FROM whitelist WHERE {where_clause}"

            async with db.execute(query) as cursor:
                the_boys = [row[0] async for row in cursor]
                return ", ".join(sorted(the_boys, key=str.casefold))

    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"
