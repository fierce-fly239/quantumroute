"""Settings that come from the environment.

Two knobs, both optional:

  TOMTOM_API_KEY       needed only when the TomTom travel-time provider is used.
  QR_TRAVEL_PROVIDER   "simulated" (default) or "tomtom". Which source the web
                       app's graphs and solves use unless a request says otherwise.

Values are read from the process environment first, then from `backend/.env` if
that file exists. The file is git-ignored: the key must never be committed.
python-dotenv would do this in one line, but it is one more package for the
non-technical teammate's setup to fail on, and the parser below is eight lines.
"""

import os
from pathlib import Path
from typing import Dict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "snapshots"


def _read_env_file() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not ENV_FILE.is_file():
        return out
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


_FILE = _read_env_file()


def setting(name: str, default: str = "") -> str:
    return os.environ.get(name) or _FILE.get(name) or default


def tomtom_key() -> str:
    return setting("TOMTOM_API_KEY")


def default_provider() -> str:
    value = setting("QR_TRAVEL_PROVIDER", "simulated").lower()
    return value if value in ("simulated", "tomtom") else "simulated"
