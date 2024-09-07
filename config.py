import os
from typing import Dict, List, Optional, TypedDict

LOCAL_SERVER_IP = os.getenv("REMOTE_SERVER_IP")
REMOTE_SERVER_IP = os.getenv("HOME_SERVER_IP")

assert isinstance(LOCAL_SERVER_IP, str)
assert isinstance(REMOTE_SERVER_IP, str)


class ServerDict(TypedDict):
    name: str
    ip: str
    port: int
    gists: Optional[Dict[str, str]]


# NOTE: Serveres with a remote IP will only work with steam command get_playerlist
# Im not really sure how I want to deal with remote vs local servers
# Maybe I can setup rcon control in the future? Or maybe I shouldn't even deal with remote
# With this program, not really sure right now
# One thing I do know is a lot of code has to change if I restructure this main data type
SERVER_DATA: List[ServerDict] = [
    {
        "name": "vanilla",
        "ip": REMOTE_SERVER_IP,
        "port": 16261,
        "gists": None,
    },
    # {
    #     "name": "test_pzserver",
    #     "ip": LOCAL_SERVER_IP,
    #     "port": 17261,
    #     "gists": None,
    # },
    {
        "name": "pel_pzserver",
        "ip": LOCAL_SERVER_IP,
        "port": 16261,
        "gists": {
            "modlist": "368a4d58ab96964575dfb292c597810c",
            "sandbox": "f6f6163393c21e92a5147b9e535eb0d3",
        },
    },
    {
        "name": "medium_pzserver",
        "ip": LOCAL_SERVER_IP,
        "port": 16267,
        "gists": {
            "modlist": "92bb4ee5f74bf724fff11e2e8642c2dd",
            "sandbox": "9fba49d384131d76b147e2a8d087394e",
        },
    },
    {
        "name": "heavy_pzserver",
        "ip": LOCAL_SERVER_IP,
        "port": 16265,
        "gists": {
            "modlist": "bd6cd4aa1fc6571260be63654f0995db",
            "sandbox": "cc814a2b2c1978ca119cb658bba3114d",
        },
    },
]

LOCAL_SERVER_NAMES = [
    server["name"] for server in SERVER_DATA if server["ip"] == LOCAL_SERVER_IP
]

ALL_SERVER_NAMES = [server["name"] for server in SERVER_DATA]
