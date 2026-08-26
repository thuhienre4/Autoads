import json
from pathlib import Path
from typing import Any


STORE_PATH = Path(__file__).resolve().parents[2] / ".local" / "google_oauth_session.json"


def _load_session() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return {"user": None, "token": None, "scopes": ""}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"user": None, "token": None, "scopes": ""}


oauth_session: dict[str, Any] = _load_session()
oauth_session.setdefault("user", None)
oauth_session.setdefault("token", None)
oauth_session.setdefault("scopes", "")


def save_oauth_session() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(oauth_session, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_oauth_session() -> None:
    oauth_session.update({
    "user": None,
    "token": None,
    "scopes": "",
    })
    if STORE_PATH.exists():
        STORE_PATH.unlink()
