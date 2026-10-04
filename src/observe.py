"""Pure-ASGI observer around the upstream app.

The middleware buffers each ``POST /v1/systemone`` body itself, so the
``metadata`` key upstream ignores is visible here; it replays the body to the
inner app exactly once and captures the response body on the way out. Every
other scope passes straight through.
"""
import json
import logging
import time

from laya.serve import MAX_BODY_BYTES

from .recorder import RequestRecord, canonical_input_hash, utc_now_iso
from .request_log import format_exchange

_logger = logging.getLogger("src.requests")

_MISSING = object()
_METADATA_NOT_OBJECT = "'metadata' must be a JSON object"
_CLIENT_ID_INVALID = "'metadata.clientId' must be a non-empty string"
_BODY_TOO_LARGE = "request body too large"


class RequestObserverMiddleware:
    def __init__(self, app, config, recorder=None):
        self.app = app
        self.config = config
        self.recorder = recorder

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            try:
                await self.app(scope, receive, send)
            finally:
                if self.recorder is not None:
                    self.recorder.close()
            return
        if not _is_observed(scope):
            await self.app(scope, receive, send)
            return
        await self._observe(scope, receive, send)

    async def _observe(self, scope, receive, send):
        started = time.perf_counter()
        body, too_large = await _read_capped_body(receive)
        if too_large:
            response_body = {"detail": _BODY_TOO_LARGE}
            await _send_json(send, 413, response_body)
            self._log(scope, started, 413, None, None, response_body)
            return

        request_body = _parse_json_object(body)
        metadata = _MISSING
        client_id = None
        if request_body is not None:
            metadata = request_body.get("metadata", _MISSING)
            if metadata is not _MISSING:
                client_id, error = _validate_metadata(metadata)
                if error is not None:
                    response_body = {"detail": error}
                    await _send_json(send, 400, response_body)
                    self._log(scope, started, 400, request_body, metadata, response_body)
                    return

        captured = _ResponseCapture(send)
        await self.app(scope, _replay(body, receive), captured.send)
        response_body = captured.json()

        self._log(scope, started, captured.status, request_body, metadata, response_body)
        if client_id is not None and captured.status == 200:
            self._record(request_body, metadata, client_id, response_body)

    def _record(self, request_body, metadata, client_id, response_body):
        if self.recorder is None or response_body is None:
            return
        routing = response_body.get("routing")
        entry = RequestRecord(
            recorded_at=utc_now_iso(),
            client_id=client_id,
            model=routing.get("model") if isinstance(routing, dict) else None,
            content_hash=canonical_input_hash(request_body.get("state"), request_body.get("questions")),
            metadata=json.dumps(metadata, ensure_ascii=False),
            request=json.dumps(request_body, ensure_ascii=False),
            response=json.dumps(response_body, ensure_ascii=False),
        )
        self.recorder.record(entry)

    def _log(self, scope, started, status, request_body, metadata, response_body):
        if not self.config.debug_requests:
            return
        block = format_exchange(
            timestamp=utc_now_iso(),
            method=scope["method"],
            path=scope["path"],
            status=status,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            request_body=request_body,
            metadata=None if metadata is _MISSING else metadata,
            response_body=response_body,
            max_chars=self.config.debug_max_chars,
        )
        _logger.info(block)


def _is_observed(scope) -> bool:
    return (scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/v1/systemone")


async def _read_capped_body(receive):
    chunks = []
    total = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b"".join(chunks), False
        chunk = message.get("body", b"")
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            return b"", True
        chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks), False


def _parse_json_object(body):
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _validate_metadata(metadata):
    if not isinstance(metadata, dict):
        return None, _METADATA_NOT_OBJECT
    client_id = metadata.get("clientId")
    if not isinstance(client_id, str) or not client_id.strip():
        return None, _CLIENT_ID_INVALID
    return client_id.strip(), None


def _replay(body, receive):
    sent = False

    async def replay():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


async def _send_json(send, status, payload):
    body = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii"))],
    })
    await send({"type": "http.response.body", "body": body, "more_body": False})


class _ResponseCapture:
    def __init__(self, send):
        self._send = send
        self.status = None
        self._chunks = []

    async def send(self, message):
        if message["type"] == "http.response.start":
            self.status = message["status"]
        elif message["type"] == "http.response.body":
            self._chunks.append(message.get("body", b""))
        await self._send(message)

    def json(self):
        try:
            return json.loads(b"".join(self._chunks))
        except (ValueError, UnicodeDecodeError):
            return None
