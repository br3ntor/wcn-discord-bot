from typing import Optional

import aiosqlite


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
    async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT username FROM whitelist WHERE accesslevel='admin'"
        ) as cursor:
            the_boys = []
            async for row in cursor:
                the_boys.append(row[0])
            return ", ".join(sorted(the_boys, key=str.casefold))
