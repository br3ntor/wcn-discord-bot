import os
from typing import Optional

import aiosqlite

# TODO: Maybe all of these should only output the raw call, half do half dont


def check_db_file(server: str) -> tuple[bool, str]:
    path = f"/home/{server}/Zomboid/db/pzserver.db"
    if not os.path.exists(path):
        error_message = f"File does not exist:\n{path}"
        print(error_message)
        return False, f"File does not exist for {server} server"
    return True, path


async def get_user(server: str, username: str) -> Optional[aiosqlite.Row] | str:
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


async def get_banned_user(server: str, steamid: str) -> Optional[aiosqlite.Row] | str:
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


async def get_admins(server: str) -> str:
    file_exists, result = check_db_file(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT username FROM whitelist WHERE accesslevel='admin'"
            ) as cursor:
                the_boys = []
                async for row in cursor:
                    the_boys.append(row[0])
                return ", ".join(sorted(the_boys, key=str.casefold))
    except aiosqlite.Error as e:
        print(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"


async def reset_user_password(server: str, player: str) -> str:
    file_exists, result = check_db_file(server)
    if not file_exists:
        return result

    try:
        async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
            async with db.execute(
                "SELECT * FROM whitelist WHERE username=?", [player]
            ) as cursor:
                user_row = await cursor.fetchone()
                if user_row is None:
                    await db.close()
                    print("No user found")
                    return f"Couldn't find user {player} on the zomboid server."

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
                    return (
                        f"**{player}**'s password has been reset on the **{server}** server. "
                        "They may login with any new password."
                    )
                else:
                    print("Something went wrong")
                    return "Something went wrong, contact brent"
    except aiosqlite.Error as e:
        print(f"Database error occurred: {e}")
        return f"Error accessing database for {server} server"
