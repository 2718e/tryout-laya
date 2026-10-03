"""Request storage: the record shape, the recorder interface, and SQLite."""
import hashlib
import json
import logging
import os
import queue
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

_logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id           INTEGER PRIMARY KEY,
    recorded_at  TEXT    NOT NULL,
    client_id    TEXT    NOT NULL,
    model        TEXT,
    content_hash TEXT    NOT NULL,
    metadata     TEXT    NOT NULL,
    request      TEXT    NOT NULL,
    response     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS requests_client_time    ON requests(client_id, recorded_at);
CREATE INDEX IF NOT EXISTS requests_client_content ON requests(client_id, content_hash);
"""

_INSERT = """
INSERT INTO requests
    (recorded_at, client_id, model, content_hash, metadata, request, response)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_STOP = object()


@dataclass(frozen=True)
class RequestRecord:
    recorded_at: str
    client_id: str
    model: Optional[str]
    content_hash: str
    metadata: str
    request: str
    response: str


class RequestRecorder(Protocol):
    def record(self, entry: RequestRecord) -> None: ...
    def close(self) -> None: ...


def utc_now_iso() -> str:
    """ISO-8601 UTC with millisecond precision and a trailing Z."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (now.microsecond // 1000)


def canonical_input_hash(state, questions) -> str:
    payload = json.dumps({"state": state, "questions": questions},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SqliteRequestRecorder:
    """Write records to SQLite from one dedicated daemon thread.

    ``record()`` only enqueues, so the event loop never waits on disk I/O.
    """

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.executescript(_SCHEMA)
        self._connection.commit()
        self._queue: "queue.Queue" = queue.Queue()
        self._close_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = threading.Thread(
            target=self._write_loop, name="tryout-laya-recorder", daemon=True)
        self._thread.start()

    def record(self, entry: RequestRecord) -> None:
        if self._thread is None:
            return
        self._queue.put(entry)

    def close(self) -> None:
        with self._close_lock:
            if self._thread is None:
                return
            self._queue.put(_STOP)
            self._thread.join()
            self._thread = None
            self._connection.close()

    def _write_loop(self) -> None:
        while True:
            entry = self._queue.get()
            if entry is _STOP:
                return
            try:
                self._connection.execute(_INSERT, (
                    entry.recorded_at, entry.client_id, entry.model,
                    entry.content_hash, entry.metadata, entry.request, entry.response,
                ))
                self._connection.commit()
            except Exception:
                _logger.warning("failed to record request; dropping it", exc_info=True)
