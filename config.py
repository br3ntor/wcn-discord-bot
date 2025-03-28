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

    SERVER_DATA: List[ServerConfig] = [
        {
            "system_user": "test_pzserver",
            "server_name": "Test_Server",
            "port": 17261,
            "gists": {"modlist": "f4ae50a891ec2643bddc12ba140b4183"},
        },
        {
            "system_user": "pel_pzserver",
            "server_name": "Light",
            "port": 16261,
            "gists": {
                "modlist": "368a4d58ab96964575dfb292c597810c",
                "sandbox": "f6f6163393c21e92a5147b9e535eb0d3",
            },
        },
        {
            "system_user": "medium_pzserver",
            "server_name": "Medium",
            "port": 16267,
            "gists": {
                "modlist": "92bb4ee5f74bf724fff11e2e8642c2dd",
                "sandbox": "9fba49d384131d76b147e2a8d087394e",
            },
        },
        {
            "system_user": "heavy_pzserver",
            "server_name": "Heavy",
            "port": 16265,
            "gists": {
                "modlist": "bd6cd4aa1fc6571260be63654f0995db",
                "sandbox": "cc814a2b2c1978ca119cb658bba3114d",
            },
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
