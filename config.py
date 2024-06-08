import os

LOCAL_SERVER_IP = os.getenv("REMOTE_SERVER_IP")
REMOTE_SERVER_IP = os.getenv("HOME_SERVER_IP")

# NOTE: Serveres with a remote IP will only work with steam command get_playerlist
# Im not really sure how I want to deal with remote vs local servers
# Maybe I can setup rcon control in the future? Or maybe I shouldn't even deal with remote
# With this program, not really sure right now
# One thing I do know is a lot of code has to change if I restructure this main data type
SERVER_DATA = [
    {
        "name": "vanilla",
        "ip": REMOTE_SERVER_IP,
        "port": 16261,
        "gists": None,
    },
    {
        "name": "test_pzserver",
        "ip": LOCAL_SERVER_IP,
        "port": 17261,
        "gists": None,
    },
    {
        "name": "pel_pzserver",
        "ip": LOCAL_SERVER_IP,
        "port": 16261,
        "gists": {"modlist": "368a4d58ab96964575dfb292c597810c", "sandbox": ""},
    },
    {
        "name": "heavy_pzserver",
        "ip": LOCAL_SERVER_IP,
        "port": 16265,
        "gists": {"modlist": "bd6cd4aa1fc6571260be63654f0995db", "sandbox": ""},
    },
]

LOCAL_SERVER_NAMES = [
    server["name"] for server in SERVER_DATA if server["ip"] == LOCAL_SERVER_IP
]
