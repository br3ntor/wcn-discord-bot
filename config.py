import os
from typing import Dict, List, Optional, TypedDict

SERVER_PUB_IP = os.getenv("SERVER_PUB_IP")


class ServerDict(TypedDict):
    username: str
    servername: str
    ip: str
    port: int
    gists: Optional[Dict[str, str]]


SERVER_DATA: List[ServerDict] = [
    {
        "username": "pzserver",
        "servername": "Vanilla",
        "ip": SERVER_PUB_IP,
        "port": 16261,
        "gists": None,
    },
    # {
    #     "name": "medium_pzserver",
    #     "ip": LOCAL_SERVER_IP,
    #     "port": 16267,
    #     "gists": {
    #         "modlist": "92bb4ee5f74bf724fff11e2e8642c2dd",
    #         "sandbox": "9fba49d384131d76b147e2a8d087394e",
    #     },
    # },
]

# Mapping the servers name to the linux username the server runs under
SERVER_NAMES = {srv["servername"]: srv["username"] for srv in SERVER_DATA}
