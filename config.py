import os

REMOTE_SERVER_IP = os.getenv("REMOTE_SERVER_IP")
HOME_SERVER_IP = os.getenv("HOME_SERVER_IP")

SERVER_DATA = [
    {
        "name": "vanilla",
        "gists": None,
        "ip": HOME_SERVER_IP,
        "port": 16261,
    },
    {
        "name": "test_pzserver",
        "gists": None,
        "ip": REMOTE_SERVER_IP,
        "port": 17261,
    },
    {
        "name": "pel_pzserver",
        "gists": {"modlist": "368a4d58ab96964575dfb292c597810c", "sandbox": ""},
        "ip": REMOTE_SERVER_IP,
        "port": 16261,
    },
    {
        "name": "heavy_pzserver",
        "gists": {"modlist": "bd6cd4aa1fc6571260be63654f0995db", "sandbox": ""},
        "ip": REMOTE_SERVER_IP,
        "port": 16265,
    },
]
