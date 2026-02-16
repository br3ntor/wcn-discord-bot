import json
import os
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

print("Loading Config...")

CONFIG_DIR = Path(__file__).parent.parent / "config"


# This program is setup for one or more project zomboid servers running
# on the same machine with a single IP. Each game instance is run under
# its own user on a seperate port and managed as a systemd service.
# TODO: Switch to using RCON for issuing server commands maybe
class ServerConfig(TypedDict):
    system_user: str
    server_name: str
    port: int
    gists: Optional[Dict[str, str]]
    discord_ids: Optional[Dict[str, int]]


class CogConfig(TypedDict):
    enabled: bool
    class_name: str
    description: str
    requires_database: bool


def load_server_data(filepath: str) -> List[ServerConfig]:
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Server config file not found at {filepath}, using empty list.")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {filepath}, using empty list.")
        return []


def load_cogs_config(filepath: str) -> Dict[str, CogConfig]:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return data.get("cogs", {})
    except FileNotFoundError:
        print(f"Cogs config file not found at {filepath}, using empty config.")
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {filepath}, using empty config.")
        return {}


# TODO: Setup config so init only populates available commands based on populated env vars
class Config:
    # Required Env Vars - Program shouldn't run without these
    ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))
    MY_GUILD = int(os.getenv("MY_GUILD", 0))
    PZ_ADMIN_ROLE_ID = int(os.getenv("PZ_ADMIN_ROLE_ID", 0))
    MOD_CHANNEL = int(os.getenv("MOD_CHANNEL", 0))
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

    # Optional Env Vars - TODO: Commands that depend on these shouldn't be made available
    # Maybe a later task could be a status function the user could see to see bot setup
    GITHUB_PAT = os.getenv("GITHUB_PAT")
    SERVER_PUB_IP = os.getenv("SERVER_PUB_IP")
    STEAM_KEY = os.getenv("STEAM_WEBAPI")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    SETTINGS_PATH = os.getenv("SETTINGS_PATH")

    SERVER_DATA: List[ServerConfig] = load_server_data(str(CONFIG_DIR / "servers.json"))

    # Map server name to system user.
    SYSTEM_USERS = {srv["server_name"]: srv["system_user"] for srv in SERVER_DATA}

    # Map system user to server name.
    SERVER_NAMES = {srv["system_user"]: srv["server_name"] for srv in SERVER_DATA}

    COGS_CONFIG: Dict[str, CogConfig] = load_cogs_config(str(CONFIG_DIR / "cogs.json"))

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
        if not Config.MOD_CHANNEL:
            raise EnvironmentError("MOD_CHANNEL environment variable is not set")
        return True
