"""Observer settings, read from the environment once at startup."""
import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_REQUESTS_DB = ".logs/requests.db"
_TRUTHY = ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ObserverConfig:
    debug_requests: bool = False
    debug_max_chars: int = 500
    requests_db: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ObserverConfig":
        return cls(
            debug_requests=_env_flag("LAYA_DEBUG_REQUESTS"),
            debug_max_chars=_env_positive_int("LAYA_DEBUG_MAX_CHARS", 500),
            requests_db=_requests_db_path(),
        )


def _env_flag(name: str) -> bool:
    raw = os.environ.get(name)
    return raw is not None and raw.strip().lower() in _TRUTHY


def _env_positive_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _requests_db_path() -> Optional[str]:
    raw = os.environ.get("LAYA_REQUESTS_DB")
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    return DEFAULT_REQUESTS_DB if value.lower() in _TRUTHY else value
