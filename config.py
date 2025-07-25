import os
from typing import Dict, List, Optional, TypedDict

print("Loading Config...")


# This program is setup for one or more project zomboid servers running
# on the same machine with a single IP. Each game instance is run under
# its own user on a seperate port and managed as a systemd service.
class ServerConfig(TypedDict):
    system_user: str
    server_name: str
    port: int
    gists: Optional[Dict[str, str]]


# TODO: Setup config so init only populates available commands based on populated env vars
class Config:
    # Required Env Vars - Program shouldn't run without these
    ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))
    MY_GUILD = int(os.getenv("MY_GUILD", 0))
    PZ_ADMIN_ROLE_ID = int(os.getenv("PZ_ADMIN_ROLE_ID", 0))
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

    # Optional Env Vars - TODO: Commands that depend on these shouldn't be made available
    # Maybe a later task could be a status function the user could see to see bot setup
    GITHUB_PAT = os.getenv("GITHUB_PAT")
    SERVER_PUB_IP = os.getenv("SERVER_PUB_IP")
    STEAM_KEY = os.getenv("STEAM_WEBAPI")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    SETTINGS_PATH = os.getenv("SETTINGS_PATH")

    SERVER_DATA: List[ServerConfig] = [
        {
            "system_user": "pzserver",
            "server_name": "Modded",
            "port": 16261,
            "gists": {
                "modlist": "9d174805e9ff5939e83128b7f5b085fe",
                "sandbox": "425e3a551d4ef5463944f8ae38d6bb7f",
            },
        },
        {
            "system_user": "test_pzserver",
            "server_name": "Test",
            "port": 17261,
            "gists": None,
        },
    ]

    # Map server name to system user.
    SYSTEM_USERS = {srv["server_name"]: srv["system_user"] for srv in SERVER_DATA}

    # Map system user to server name.
    SERVER_NAMES = {srv["system_user"]: srv["server_name"] for srv in SERVER_DATA}

    @staticmethod
    def validate():
        if not Config.ANNOUNCE_CHANNEL:
            raise EnvironmentError("ANNOUNCE_CHANNEL environment variable is not set")
        if not Config.DISCORD_TOKEN:
            raise EnvironmentError("DISCORD_TOKEN environment variable is not set")
        if not Config.MY_GUILD:
            raise EnvironmentError("MY_GUILD environment variable is not set")
        if not Config.PZ_ADMIN_ROLE_ID:
            raise EnvironmentError("PZ_ADMIN_ROLE_ID environment variable is not set")
        return True
