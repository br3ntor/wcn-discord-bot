## WCN Project Zomboid Discord Bot

This is a bot to control one more more Project Zomboid servers on a single machine that have been installed with LinuxGSM.

The server commands are issued with RCON and restarts use systemD.

## Development

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Checks
ruff check .
black --check .
mypy <scoped paths>
pytest
```

`mypy` is configured in `pyproject.toml` but has pre-existing errors repo-wide — run it scoped to the files you are touching.

