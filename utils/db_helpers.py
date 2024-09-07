import os
from typing import Optional

import aiosqlite

# TODO: Maybe all of these should only output the raw call, half do half dont


async def get_user(server: str, username: str) -> Optional[aiosqlite.Row]:
    """Return the db row for a player."""
    async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT * FROM whitelist WHERE username=?", [username]
        ) as cursor:
            return await cursor.fetchone()


async def get_banned_user(server: str, steamid: str) -> Optional[aiosqlite.Row]:
    """Return the db row for a banned player."""
    async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT * FROM bannedid WHERE steamid=?", [steamid]
        ) as cursor:
            return await cursor.fetchone()


async def get_admins(server: str) -> str:
    # This can happen when in the middle of setting up server
    # after deleting old files and before starting server program.
    path = f"/home/{server}/Zomboid/db/pzserver.db"
    if not os.path.exists(path):
        print(f"File does not exist:\n${path}")
        return f"File does not exist for ${server} server"

    async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT username FROM whitelist WHERE accesslevel='admin'"
        ) as cursor:
            the_boys = []
            async for row in cursor:
                the_boys.append(row[0])
            return ", ".join(sorted(the_boys, key=str.casefold))


async def reset_user_password(server: str, player: str) -> str:
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
