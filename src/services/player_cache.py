import logging
import time

from src.services.pz_server import pz_players

logger = logging.getLogger(__name__)


class PlayerCache:
    """Caches player lists per server with configurable TTL."""

    def __init__(self, ttl: int = 15):
        self._cache: dict[str, dict] = {}
        self._ttl = ttl

    async def get_players(self, system_user: str) -> list[str] | None:
        """Return cached players if fresh, otherwise fetch and cache new data."""
        cache_entry = self._cache.get(system_user)
        now = time.time()

        if cache_entry and (now - cache_entry["timestamp"]) < self._ttl:
            return cache_entry["players"]

        try:
            players = await pz_players(system_user)
        except Exception as e:
            logger.error("PlayerCache RCON failed: %s", e)
            return cache_entry["players"] if cache_entry else None

        if players is None:
            return cache_entry["players"] if cache_entry else None

        self._cache[system_user] = {"players": players, "timestamp": now}
        return players
