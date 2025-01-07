import os
from typing import Dict, List, Optional, TypedDict


# This program is setup for one or more project zomboid servers running
# on the same machine with a single IP. Each game instance is run under
# its own user on a seperate port and managed as a systemd service.
class ServerConfig(TypedDict):
    system_user: str
    display_name: str
    port: int
    gists: Optional[Dict[str, str]]


# TODO: Setup config so init only populates available commands based on populated env vars
class Config:
    # Required Env Vars
    ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))
    MY_GUILD = int(os.getenv("MY_GUILD", 0))

    # Optional Env Vars
    SERVER_PUB_IP = os.getenv("SERVER_PUB_IP")
    ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))
    MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", 0))
    STEAM_KEY = os.getenv("STEAM_WEBAPI")
    GITHUB_PAT = os.getenv("GITHUB_PAT")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

    SERVER_DATA: List[ServerConfig] = [
        {
            "system_user": "pel_pzserver",
            "display_name": "Vanilla_2",
            "port": 16261,
            "gists": None,
        },
        {
            "system_user": "medium_pzserver",
            "display_name": "Medium",
            "port": 16267,
            "gists": {
                "modlist": "92bb4ee5f74bf724fff11e2e8642c2dd",
                "sandbox": "9fba49d384131d76b147e2a8d087394e",
            },
        },
        {
            "system_user": "heavy_pzserver",
            "display_name": "Heavy",
            "port": 16265,
            "gists": {
                "modlist": "bd6cd4aa1fc6571260be63654f0995db",
                "sandbox": "cc814a2b2c1978ca119cb658bba3114d",
            },
        },
    ]

    # Mapping the servers name to the linux username the server runs under
    SERVER_NAMES = {srv["display_name"]: srv["system_user"] for srv in SERVER_DATA}

    @staticmethod
    def validate():
        if not Config.SERVER_PUB_IP:
            raise EnvironmentError("SERVER_PUB_IP environment variable is not set")
        if not Config.MOD_ROLE_ID:
            raise EnvironmentError("MOD_ROLE_ID environment variable is not set")
        if not Config.ANNOUNCE_CHANNEL:
            raise EnvironmentError("ANNOUNCE_CHANNEL environment variable is not set")
