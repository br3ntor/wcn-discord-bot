import os
from enum import Enum
from typing import Optional

import aiosqlite

from src.utils.server_utils import get_game_version


# I was going to generalize this to the other functions in here but dont have time right now so
# my enum will only be used in the get password function for now.
class PasswordResetStatus(Enum):
    SUCCESS = 0
    DB_FILE_NOT_FOUND = 1
    USER_NOT_FOUND = 2
    DATABASE_ACCESS_ERROR = 3
    UNKNOWN_ERROR = 4


# TODO: Maybe all of these should only output the raw call, half do half dont
def check_db_file(server: str) -> tuple[bool, str]:
    path = f"/home/{server}/Zomboid/db/pzserver.db"
    if not os.path.exists(path):
        error_message = f"File does not exist:\n{path}"
        print(error_message)
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
        print(f"Database error occurred: {e}")
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
        print(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


# async def get_banned_user(server: str, steamid: str) -> Optional[aiosqlite.Row] | str:
# Why annotate the return if it seems to be inferred, right?
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
        print(f"Database error occurred: {e}")
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
        print(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def get_admins(server: str) -> str:
    file_exists, result = check_db_file(server)
    if not file_exists:
        return result

    # 1. Determine the query logic based on version
    game_version = get_game_version(server)

    # Default for B42 and others
    where_clause = "role='7'"

    # Override for B41
    if game_version == "B41":
        where_clause = "accesslevel='admin'"

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            # 2. Inject the dynamic clause, safe because I'm making it right above
            # it's not anything user can inject. Yea I'm in this situation in the first place
            # because I'm listening to the AI slop output!
            query = f"SELECT username FROM whitelist WHERE {where_clause}"

            async with db.execute(query) as cursor:
                the_boys = [row[0] async for row in cursor]
                return ", ".join(sorted(the_boys, key=str.casefold))

    except aiosqlite.Error as e:
        print(f"Database error occurred: {e}")
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
                    print("No user found")
                    return PasswordResetStatus.USER_NOT_FOUND

                print(f"User {player} has been found")
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
                    print(f"reset {player} pwd")
                    return PasswordResetStatus.SUCCESS
                else:
                    print("Something went wrong")
                    return PasswordResetStatus.UNKNOWN_ERROR
    except aiosqlite.Error as e:
        print(f"Database error occurred: {e}")
        return PasswordResetStatus.DATABASE_ACCESS_ERROR


async def is_db_locked(db_path):
    """
    Returns True if the database is locked.
    Uses a tiny timeout to check availability without hanging the bot.
    """
    if not os.path.exists(db_path):
        return False  # Or handle as error

    try:
        # We set a very short timeout (0.1s) for the connection itself
        async with aiosqlite.connect(db_path, timeout=0.1) as db:
            # Attempt to start a write-intent transaction
            await db.execute("BEGIN IMMEDIATE")
            await db.rollback()
            return False  # Success! The database is NOT locked.
    except Exception as e:
        # SQLite raises an OperationalError when the DB is locked
        if "locked" in str(e).lower():
            return True
        # If it's a different error, you might want to log it
        print(f"Database error: {e}")
        return True
