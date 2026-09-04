import json
import os
from pathlib import Path
from typing import Any

from app.core.config import settings


DEFAULT_STORE_PATH = Path(__file__).resolve().parents[2] / ".local" / "google_oauth_session.json"


def resolve_store_path(
    configured_path: str | None = None,
    railway_volume_path: str | None = None,
) -> Path:
    """Resolve OAuth storage, preferring a Railway persistent volume."""
    if configured_path and configured_path.strip():
        return Path(configured_path.strip())
    if railway_volume_path and railway_volume_path.strip():
        return Path(railway_volume_path.strip()) / "google_oauth_session.json"
    return DEFAULT_STORE_PATH


STORE_PATH = resolve_store_path(
    settings.GOOGLE_OAUTH_STORE_PATH,
    settings.RAILWAY_VOLUME_MOUNT_PATH,
)


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
    temporary_path = STORE_PATH.with_suffix(f"{STORE_PATH.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(oauth_session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(STORE_PATH)
    try:
        os.chmod(STORE_PATH, 0o600)
    except OSError:
        pass


def oauth_store_is_persistent() -> bool:
    return bool(settings.GOOGLE_OAUTH_STORE_PATH or settings.RAILWAY_VOLUME_MOUNT_PATH)


def clear_oauth_session() -> None:
    oauth_session.update({
    "user": None,
    "token": None,
    "scopes": "",
    })
    if STORE_PATH.exists():
        STORE_PATH.unlink()
