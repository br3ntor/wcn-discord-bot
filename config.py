import os

REMOTE_SERVER_IP = os.getenv("REMOTE_SERVER_IP")
HOME_SERVER_IP = os.getenv("HOME_SERVER_IP")

SERVERNAMES = ["test_pzserver", "pel_pzserver", "heavy_pzserver"]
SERVER_DATA = [
    {
        "name": "test_pzserver",
        "gists": {"modlist": "", "sandbox": ""},
        "ip": REMOTE_SERVER_IP,
        "port": 17261,
    },
    {
        "name": "vanilla",
        "gists": {"modlist": "", "sandbox": ""},
        "ip": HOME_SERVER_IP,
        "port": 16261,
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
