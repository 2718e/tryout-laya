"""Entry point: the upstream Laya app wrapped in the request observer.

``uv run python -m tryout_laya.server`` is what ``make serve`` runs.
"""
import logging
import os
from typing import Any, Optional

from laya.serve import _resolve_port, create_app

from .config import ObserverConfig
from .observe import RequestObserverMiddleware
from .recorder import SqliteRequestRecorder


def build_observed_app(router: Optional[Any] = None):
    config = ObserverConfig.from_env()
    recorder = SqliteRequestRecorder(config.requests_db) if config.requests_db else None
    return RequestObserverMiddleware(create_app(router), config, recorder)


def _configure_request_logging() -> None:
    level = logging.getLevelNamesMapping().get(
        os.environ.get("LAYA_LOG_LEVEL", "info").upper(), logging.INFO)
    logger = logging.getLogger("tryout_laya.requests")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def main() -> None:
    import uvicorn

    _configure_request_logging()
    uvicorn.run(
        build_observed_app(),
        host=os.environ.get("LAYA_HOST", "0.0.0.0"),
        port=_resolve_port(),
        log_level=os.environ.get("LAYA_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
