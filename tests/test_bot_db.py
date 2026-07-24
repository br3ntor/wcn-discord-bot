import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import aiosqlite

from src.services import bot_db


class FakeUser:
    def __init__(self, user_id: int, name: str, roles: list):
        self.id = user_id
        self.name = name
        self.roles = roles

    def __str__(self):
        return self.name


def make_interaction(
    user_id: int = 123456789,
    user_name: str = "testuser",
    roles: list | None = None,
    guild_id: int | None = 987654321,
    channel_id: int | None = 555555555,
):
    """Build a minimal fake interaction for log_command_history."""
    if roles is None:
        roles = [
            SimpleNamespace(id=1, name="@everyone", is_default=lambda: True),
            SimpleNamespace(id=42, name="PZ Admin", is_default=lambda: False),
        ]
    return SimpleNamespace(
        user=FakeUser(user_id, user_name, roles),
        guild_id=guild_id,
        channel_id=channel_id,
    )


class CommandHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        bot_db.db_path = Path(self.temp_dir.name) / "bot_database.db"
        await bot_db.init_db()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def log(self, command_name, steam_id="76561198000000000", **kwargs):
        kwargs.setdefault("player_name", "TestPlayer")
        kwargs.setdefault("server_name", "Server One")
        return await bot_db.log_command_history(
            make_interaction(),
            command_name,
            steam_id=steam_id,
            **kwargs,
        )

    async def test_log_command_history_stores_row_data(self):
        interaction = make_interaction()
        self.assertTrue(
            await bot_db.log_command_history(
                interaction,
                "heal_player",
                server_name="Server One",
                steam_id="76561198000000000",
                player_name="TestPlayer",
                arguments={"server": "Server One", "player": "TestPlayer"},
            )
        )

        async with aiosqlite.connect(bot_db.db_path) as db:
            async with db.execute(
                "SELECT command_name, discord_user_id, discord_username, discord_roles,"
                " guild_id, channel_id, server_name, steam_id, player_name, arguments,"
                " success FROM command_history"
            ) as cursor:
                row = await cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "heal_player")
        self.assertEqual(row[1], "123456789")
        self.assertEqual(row[2], "testuser")
        # @everyone must be excluded from stored roles
        self.assertEqual(json.loads(row[3]), [{"id": "42", "name": "PZ Admin"}])
        self.assertEqual(row[4], "987654321")
        self.assertEqual(row[5], "555555555")
        self.assertEqual(row[6], "Server One")
        self.assertEqual(row[7], "76561198000000000")
        self.assertEqual(row[8], "TestPlayer")
        self.assertEqual(
            json.loads(row[9]), {"server": "Server One", "player": "TestPlayer"}
        )
        self.assertEqual(row[10], 1)

    async def test_get_latest_player_command_returns_most_recent(self):
        steam_id = "76561198000000000"
        player_name = "TestPlayer"
        self.assertIsNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "heal_self", player_name
            )
        )

        await self.log("heal_self", steam_id)
        await self.log("heal_self", steam_id, success=False)
        await self.log("heal_player", steam_id)

        latest = await bot_db.get_latest_player_command(
            steam_id, "Server One", "heal_self", player_name
        )
        self.assertIsNotNone(latest)

        # Different server returns None
        self.assertIsNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server Two", "heal_self", player_name
            )
        )
        # Different command returns None
        self.assertIsNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "restore_self", player_name
            )
        )

    async def test_get_latest_player_command_is_world_scoped(self):
        steam_id = "76561198000000000"
        player_name = "TestPlayer"
        await self.log("heal_self", steam_id)

        self.assertIsNotNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "heal_self", player_name
            )
        )

        # A world starting "now" excludes everything logged before it
        await bot_db.upsert_server_world(
            "Server One", datetime.now(timezone.utc) + timedelta(seconds=1)
        )
        self.assertIsNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "heal_self", player_name
            )
        )

    async def test_get_latest_player_command_is_per_character(self):
        steam_id = "76561198000000000"

        await self.log("heal_self", steam_id, player_name="admin")
        await self.log("heal_self", steam_id, player_name="br3ntor")

        self.assertIsNotNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "heal_self", "admin"
            )
        )
        self.assertIsNotNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "heal_self", "br3ntor"
            )
        )
        # Different character returns None
        self.assertIsNone(
            await bot_db.get_latest_player_command(
                steam_id, "Server One", "heal_self", "nobody"
            )
        )

    async def test_get_player_command_counts_by_character(self):
        steam_id = "76561198000000000"

        await self.log("heal_player", steam_id, player_name="admin")
        await self.log("heal_self", steam_id, player_name="admin")
        await self.log("heal_self", steam_id, player_name="br3ntor")
        await self.log("heal_self", steam_id, player_name="br3ntor")
        await self.log("restore_self", steam_id, player_name="br3ntor")
        await self.log("heal_player", steam_id, player_name="br3ntor", success=False)

        result = await bot_db.get_player_command_counts_by_character(steam_id, "Server One")
        self.assertEqual(
            result,
            {
                "admin": {"heal_player": 1, "heal_self": 1},
                "br3ntor": {"heal_self": 2, "restore_self": 1},
            },
        )


class ServerWorldTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        bot_db.db_path = Path(self.temp_dir.name) / "bot_database.db"
        await bot_db.init_db()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_upsert_and_get_world_start(self):
        started = datetime(2026, 5, 11, 19, 8, tzinfo=timezone.utc)

        self.assertIsNone(await bot_db.get_server_world_start("Server One"))

        self.assertTrue(await bot_db.upsert_server_world("Server One", started))
        self.assertEqual(
            await bot_db.get_server_world_start("Server One"), started
        )

        # Upsert overwrites with a newer world
        newer = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        await bot_db.upsert_server_world("Server One", newer)
        self.assertEqual(await bot_db.get_server_world_start("Server One"), newer)

    async def test_sync_server_worlds_uses_save_folder_birth_time(self):
        started = datetime(2026, 5, 11, 19, 8, tzinfo=timezone.utc)

        original = bot_db._stat_birth_time
        bot_db._stat_birth_time = lambda path: self._fake_stat(path, started)
        try:
            await bot_db.sync_server_worlds(
                [
                    {"server_name": "Server One", "system_user": "pzserver42"},
                    {"server_name": "Server Two", "system_user": "missing"},
                ]
            )
        finally:
            bot_db._stat_birth_time = original

        self.assertEqual(
            await bot_db.get_server_world_start("Server One"), started
        )
        # Failed stat keeps the server unrecorded
        self.assertIsNone(await bot_db.get_server_world_start("Server Two"))

    async def _fake_stat(self, path, started):
        return started if "pzserver42" in path else None


if __name__ == "__main__":
    unittest.main()
