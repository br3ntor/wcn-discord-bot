import logging
import os
from enum import Enum
from typing import Optional

import aiosqlite

from src.services.server import get_game_version

logger = logging.getLogger(__name__)


class PasswordResetStatus(Enum):
    SUCCESS = 0
    DB_FILE_NOT_FOUND = 1
    USER_NOT_FOUND = 2
    DATABASE_ACCESS_ERROR = 3
    UNKNOWN_ERROR = 4


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


async def reset_player_password(server: str, player: str) -> PasswordResetStatus:
    file_exists, _ = check_db_file(server)
    if not file_exists:
        return PasswordResetStatus.DB_FILE_NOT_FOUND

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE username=?", [player]
            ) as cursor:
                user_row = await cursor.fetchone()
                if user_row is None:
                    await db.close()
                    logger.warning("No user found")
                    return PasswordResetStatus.USER_NOT_FOUND

                logger.info(f"User {player} has been found")
                await cursor.execute(
                    "UPDATE whitelist SET password=? WHERE _rowid_=?",
                    (None, user_row[0]),
                )
                await db.commit()
                fresh_row = await cursor.execute(
                    "SELECT password FROM whitelist WHERE username=?", [player]
                )
                pwd = await fresh_row.fetchone()
                if pwd is not None and pwd[0] is None:
                    logger.info(f"reset {player} pwd")
                    return PasswordResetStatus.SUCCESS
                else:
                    logger.warning("Something went wrong")
                    return PasswordResetStatus.UNKNOWN_ERROR
    except aiosqlite.Error as e:
        logger.error(f"Database error occurred: {e}")
        return PasswordResetStatus.DATABASE_ACCESS_ERROR


async def is_db_locked(db_path):
    """
    Returns True if the database is locked.
    Uses a tiny timeout to check availability without hanging the bot.
    """
    if not os.path.exists(db_path):
        return False

    try:
        async with aiosqlite.connect(db_path, timeout=0.1) as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.rollback()
            return False
    except Exception as e:
        if "locked" in str(e).lower():
            return True
            logger.error(f"Database error: {e}")
        return True
