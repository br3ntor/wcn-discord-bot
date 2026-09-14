import unittest
from unittest.mock import AsyncMock, patch

from src.services import pz_server

PLAYER = "Bob"

GOD_ON_RESPONSE = f"User {PLAYER} is now invincible."
GOD_OFF_RESPONSE = f"User {PLAYER} is no more invincible."
PLAYER_NOT_FOUND_RESPONSE = f"User {PLAYER} not found."


class PzGodmodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_enable_b41_sends_godmode_command(self):
        send = AsyncMock(return_value=GOD_ON_RESPONSE)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, True)

        self.assertTrue(result)
        self.assertEqual(message, GOD_ON_RESPONSE)
        send.assert_awaited_once_with("TestServer", f'godmode "{PLAYER}" -true')

    async def test_enable_b42_sends_godmodeplayer_command(self):
        send = AsyncMock(return_value=GOD_ON_RESPONSE)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B42"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, True)

        self.assertTrue(result)
        self.assertEqual(message, GOD_ON_RESPONSE)
        send.assert_awaited_once_with("TestServer", f'godmodeplayer "{PLAYER}" -true')

    async def test_disable_b41_sends_godmode_command(self):
        send = AsyncMock(return_value=GOD_OFF_RESPONSE)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, False)

        self.assertTrue(result)
        self.assertEqual(message, GOD_OFF_RESPONSE)
        send.assert_awaited_once_with("TestServer", f'godmode "{PLAYER}" -false')

    async def test_disable_b42_sends_godmodeplayer_command(self):
        send = AsyncMock(return_value=GOD_OFF_RESPONSE)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B42"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, False)

        self.assertTrue(result)
        self.assertEqual(message, GOD_OFF_RESPONSE)
        send.assert_awaited_once_with("TestServer", f'godmodeplayer "{PLAYER}" -false')

    async def test_player_not_found(self):
        send = AsyncMock(return_value=PLAYER_NOT_FOUND_RESPONSE)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, True)

        self.assertFalse(result)
        self.assertEqual(message, PLAYER_NOT_FOUND_RESPONSE)

    async def test_unexpected_response(self):
        send = AsyncMock(return_value="Something went wrong.")
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, True)

        self.assertFalse(result)
        self.assertEqual(message, "Unexpected server response: Something went wrong.")

    async def test_rcon_unreachable(self):
        send = AsyncMock(return_value=None)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
        ):
            result, message = await pz_server.pz_godmode("TestServer", PLAYER, True)

        self.assertFalse(result)
        self.assertEqual(message, "Could not reach the server via RCON.")


class PzHealPlayerTests(unittest.IsolatedAsyncioTestCase):
    async def test_heal_toggles_godmode_on_then_off(self):
        send = AsyncMock(side_effect=[GOD_ON_RESPONSE, GOD_OFF_RESPONSE])
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
            patch.object(pz_server.asyncio, "sleep", new=AsyncMock()),
        ):
            result, message = await pz_server.pz_heal_player("TestServer", PLAYER)

        self.assertTrue(result)
        self.assertEqual(message, GOD_OFF_RESPONSE)
        self.assertEqual(send.await_count, 2)
        send.assert_any_await("TestServer", f'godmode "{PLAYER}" -true')
        send.assert_any_await("TestServer", f'godmode "{PLAYER}" -false')

    async def test_heal_stops_when_enable_fails(self):
        send = AsyncMock(return_value=PLAYER_NOT_FOUND_RESPONSE)
        with (
            patch.object(pz_server, "pz_send_command", send),
            patch.object(pz_server, "get_game_version", return_value="B41"),
            patch.object(pz_server.asyncio, "sleep", new=AsyncMock()),
        ):
            result, message = await pz_server.pz_heal_player("TestServer", PLAYER)

        self.assertFalse(result)
        self.assertEqual(message, PLAYER_NOT_FOUND_RESPONSE)
        self.assertEqual(send.await_count, 1)


if __name__ == "__main__":
    unittest.main()
