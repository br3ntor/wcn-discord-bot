import os
from typing import Dict, List, Optional, TypedDict

SERVER_PUB_IP = os.getenv("SERVER_PUB_IP")

# Not sure what best way to check for this env var is...
assert bool(SERVER_PUB_IP)


class ServerConfig(TypedDict):
    system_user: str
    display_name: str
    ip_address: str
    port: int
    gists: Optional[Dict[str, str]]


SERVER_DATA: List[ServerConfig] = [
    {
        "system_user": "pzserver",
        "display_name": "Vanilla",
        "ip_address": SERVER_PUB_IP,
        "port": 16261,
        "gists": None,
    },
    # {
    #     "system_user": "medium_pzserver",
    #       "display_name": "Medium",
    #     "ip": LOCAL_SERVER_IP,
    #     "port": 16267,
    #     "gists": {
    #         "modlist": "92bb4ee5f74bf724fff11e2e8642c2dd",
    #         "sandbox": "9fba49d384131d76b147e2a8d087394e",
    #     },
    # },
]

# Mapping the servers name to the linux username the server runs under
SERVER_NAMES = {srv["display_name"]: srv["system_user"] for srv in SERVER_DATA}
