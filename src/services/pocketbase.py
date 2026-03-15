import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import aiohttp
from aiohttp_sse_client import client as sse_client

from src.config import Config

logger = logging.getLogger(__name__)


class PocketBaseClient:
    url: Optional[str]
    email: Optional[str]
    password: Optional[str]
    token: Optional[str]
    client: Optional[aiohttp.ClientSession]
    _sse_task: Optional[asyncio.Task]
    _sse_client_id: Optional[str]
    _reconnect_delay: float

    def __init__(self):
        self.url = Config.POCKETBASE_URL
        self.email = Config.POCKETBASE_EMAIL
        self.password = Config.POCKETBASE_PASSWORD
        self.token = None
        self.client = None
        self._sse_task = None
        self._sse_client_id = None
        self._reconnect_delay = 5.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.client is None or self.client.closed:
            self.client = aiohttp.ClientSession()
        return self.client

    async def login(self) -> bool:
        if not Config.pocketbase_configured:
            logger.warning("PocketBase not configured")
            return False

        session = await self._get_session()
        auth_url = f"{self.url}/api/collections/bots/auth-with-password"

        try:
            async with session.post(
                auth_url,
                json={"identity": self.email, "password": self.password},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("token")
                    logger.info("PocketBase login successful")
                    return True
                else:
                    logger.error(f"PocketBase login failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"PocketBase login error: {e}")
            return False

    async def refresh_token(self) -> bool:
        if not self.token:
            return await self.login()

        session = await self._get_session()
        refresh_url = f"{self.url}/api/collections/bots/auth-refresh"

        try:
            async with session.post(
                refresh_url,
                headers={"Authorization": f"Bearer {self.token}"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("token")
                    return True
                else:
                    logger.warning(f"PocketBase token refresh failed: {resp.status}")
                    return await self.login()
        except Exception as e:
            logger.error(f"PocketBase token refresh error: {e}")
            return await self.login()

    def _auth_headers(self) -> Dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    async def get_bans(self, is_active: bool = True) -> List[Dict[str, Any]]:
        session = await self._get_session()
        filter_expr = "is_active=true" if is_active else "is_active=false"
        bans_url = f"{self.url}/api/collections/bans/records?filter={filter_expr}&perPage=100"

        try:
            async with session.get(bans_url, headers=self._auth_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
                else:
                    logger.error(f"Failed to get bans: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching bans: {e}")
            return []

    async def get_all_bans(self) -> List[Dict[str, Any]]:
        session = await self._get_session()
        bans_url = f"{self.url}/api/collections/bans/records?perPage=500"

        try:
            async with session.get(bans_url, headers=self._auth_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
                else:
                    logger.error(f"Failed to get all bans: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching all bans: {e}")
            return []

    async def create_ban(
        self,
        steamid: str,
        name: str,
        reason: str,
        server_origin: str,
        expire: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        session = await self._get_session()
        create_url = f"{self.url}/api/collections/bans/records"

        data = {
            "steamid": steamid,
            "name": name,
            "reason": reason,
            "server_origin": server_origin,
            "is_active": True,
        }

        if expire:
            data["expire"] = expire

        try:
            async with session.post(
                create_url,
                json=data,
                headers=self._auth_headers(),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Created ban for {steamid}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"Failed to create ban: {resp.status} - {error}")
                    return None
        except Exception as e:
            logger.error(f"Error creating ban: {e}")
            return None

    async def update_ban(
        self, ban_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        session = await self._get_session()
        update_url = f"{self.url}/api/collections/bans/records/{ban_id}"

        try:
            async with session.patch(
                update_url,
                json=data,
                headers=self._auth_headers(),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"Updated ban {ban_id}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"Failed to update ban: {resp.status} - {error}")
                    return None
        except Exception as e:
            logger.error(f"Error updating ban: {e}")
            return None

    async def deactivate_ban(self, ban_id: str) -> bool:
        result = await self.update_ban(ban_id, {"is_active": False})
        return result is not None

    async def health_check(self) -> bool:
        session = await self._get_session()
        health_url = f"{self.url}/api/health"

        try:
            async with session.get(health_url) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def subscribe(
        self, callback: Callable[[str, Dict[str, Any]], Any]
    ) -> None:
        if not self.token:
            if not await self.login():
                logger.error("Cannot subscribe - login failed")
                return

        self._callback = callback
        self._sse_task = asyncio.create_task(self._sse_loop())

    async def _sse_loop(self) -> None:
        while True:
            try:
                await self._run_sse()
            except Exception as e:
                logger.info(f"SSE connection closed: {e}")

            logger.info(f"Reconnecting to SSE in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def _run_sse(self) -> None:
        headers = {"Authorization": f"Bearer {self.token}"}

        async with sse_client.EventSource(
            f"{self.url}/api/realtime",
            headers=headers
        ) as event_source:
            async for event in event_source:
                if event.type == "message":
                    try:
                        data = json.loads(event.data)

                        if data.get("action") == "PB_CONNECT":
                            client_id = data.get("clientId")
                            logger.info(f"PB_CONNECT, clientId: {client_id}")
                            await self._subscribe_to_bans(client_id)

                        elif data.get("action") in ("create", "update", "delete"):
                            record = data.get("record", {})
                            action = data.get("action")
                            logger.info(f"Received {action} event: {record.get('id')}")
                            if self._callback:
                                await self._callback(action, record)
                    except json.JSONDecodeError:
                        pass

    async def _subscribe_to_bans(self, client_id: str) -> None:
        await self.refresh_token()

        session = await self._get_session()
        subscribe_url = f"{self.url}/api/realtime"
        payload = {"clientId": client_id, "subscriptions": ["bans/*"]}

        try:
            async with session.post(
                subscribe_url,
                json=payload,
                headers=self._auth_headers(),
            ) as resp:
                if resp.status == 204:
                    logger.info("Subscribed to bans collection")
                    self._reconnect_delay = 5.0
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to subscribe: {resp.status} - {error_text}")
        except Exception as e:
            logger.error(f"Error subscribing to bans: {e}")

    async def _ensure_token_valid(self) -> None:
        if self.token:
            await self.refresh_token()

    async def unsubscribe(self) -> None:
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None

    async def close(self) -> None:
        await self.unsubscribe()
        if self.client and not self.client.closed:
            await self.client.close()


pb_client = PocketBaseClient()
