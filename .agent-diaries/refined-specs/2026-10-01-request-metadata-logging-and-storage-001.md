# Request metadata, terminal visibility, and request storage

Revision: 001
Date: 2026-10-01
Status: agreed, ready to build

## Goal

Give the local Laya HTTP service three capabilities, without forking upstream `laya`:

1. **Terminal visibility** — when enabled, print the details of each `POST /v1/systemone`
   request and its response so a developer can watch what calling projects actually send.
2. **Metadata passthrough** — allow an optional arbitrary-JSON `metadata` object on the
   existing endpoint, so a caller can attach its own context (motivating use case: video
   captions plus the caption's timestamp). The default request shape is unchanged.
3. **Request storage** — persist requests that carry metadata into SQLite so the collected
   data can later be used to evaluate and tune the service.

## Non-goals

- No read/query API, CLI, or dashboard for stored data. Inspection is via the `sqlite3`
  CLI. (May come later.)
- No retention/pruning/rotation. The DB grows; pruning is manual.
- No new storage backend shipped. Only the interface plus the SQLite implementation.
- No changes to upstream `laya` (`laya/serve.py` stays untouched). `laya-serve` remains a
  working escape hatch.
- No storage of requests that lack metadata, and no storage of failed inference.
- No changes to auth, routing, question handling, or the response schema.

## Background facts (verified)

- The project is a config-only wrapper. `make serve` runs `uv run laya-serve`; all HTTP
  behavior lives in upstream `laya/serve.py::create_app()`.
- `create_app()` parses the JSON body and reads only `state`, `questions`, and `model`. Any
  other top-level key — including `metadata` — is ignored, so adding `metadata` to the
  existing endpoint is backward compatible with Jev clients and needs no upstream change.
- `create_app(router)` accepts an injected router, any object exposing `predict(...)` and
  `loaded` works; this is the seam tests use to avoid loading checkpoints.
- `laya.serve.MAX_BODY_BYTES == 2 * 1024 * 1024` (2 MB). Upstream enforces it while
  streaming the body and answers `413 {"detail": "request body too large"}`.
- SQLite in this environment is **3.53.1** with JSON1 built in; `json_extract`, expression
  indexes, and generated columns all work. Standard-library `sqlite3` is sufficient; no new
  dependency is needed.
- `json.dumps(obj, sort_keys=True, separators=(",", ":"))` is key-order stable, so it is a
  sound canonical form for hashing `state` + `questions`.

## Architecture

Add a small project package that builds the upstream app and wraps it in a pure-ASGI
observer middleware. The middleware sees the full request body (including `metadata`) and
the full response body (`answers`, `usage`, `routing`), which is everything the three
features need. Upstream code is never edited.

```
uvicorn
  └── RequestObserverMiddleware        (tryout_laya/observe.py, pure ASGI)
        └── FastAPI app                (laya.serve.create_app(router))
              └── Router               (laya.Router, from env)
```

A pure-ASGI middleware is used rather than Starlette's `BaseHTTPMiddleware` so that body
buffering and replay do not depend on framework internals: the middleware buffers the
request body itself, replays it to the inner app exactly once, and passes `lifespan` and
`websocket` scopes through untouched.

### Module layout

```
tryout_laya/
  __init__.py       # empty
  config.py         # env -> ObserverConfig dataclass
  observe.py        # RequestObserverMiddleware (validation, capture, logging, record)
  request_log.py    # formatting the terminal block
  recorder.py       # RequestRecord, RequestRecorder protocol, SqliteRequestRecorder
  server.py         # build_observed_app(router=None); main(); __main__ guard
tests/
  test_observe.py   # fast, hermetic: stub router, no checkpoint download
```

`pyproject.toml` keeps `package = false`; `uv run python -m tryout_laya.server` resolves the
package from the project root. No packaging or console-script entry is added.

## Request lifecycle

For `POST /v1/systemone` only; every other path/method and all non-HTTP scopes pass straight
through to the inner app.

1. Buffer the request body, reading at most `MAX_BODY_BYTES` (imported from
   `laya.serve`). If it exceeds the cap, answer `413 {"detail": "request body too large"}`
   locally and stop — do not call the inner app. (Upstream would reject it anyway; doing it
   here keeps the buffering bounded.)
2. Parse the body as JSON. If it is not a dict, hand it to the inner app unchanged and let
   upstream produce its own `400`.
3. If `metadata` is present, validate it (see contract below). On failure, answer `400` with
   a readable `detail` and stop. Nothing is stored.
4. Build a replay `receive` that returns the buffered body once, then delegates subsequent
   calls to the original `receive`.
5. Call the inner app, forwarding every `send` message immediately (no added latency) while
   accumulating the response status and body.
6. After the inner app returns, parse the response JSON. If `LAYA_DEBUG_REQUESTS` is on,
   log the request/response block.
7. If storage is enabled **and** the response status is `200` **and** `metadata` is present
   with a valid `clientId`, enqueue one `RequestRecord` for the writer thread.

Errors do not bypass the log: a `400`, `413`, `422`, `500`, or `401` is logged (with status
and `detail`) when verbose mode is on, but is never recorded.

## Metadata contract

- `metadata` is optional. Absent → request behaves exactly as today; nothing stored.
- When present it must be a JSON **object**; otherwise `400
  {"detail": "'metadata' must be a JSON object"}`.
- It must contain `clientId`, a **non-empty string** after stripping whitespace; otherwise
  `400 {"detail": "'metadata.clientId' must be a non-empty string"}`.
- Every other key, at any nesting depth, is arbitrary and unvalidated. No metadata-specific
  size cap is added beyond the existing 2 MB body cap.
- Validation happens **regardless of whether storage is enabled**, so the request contract
  does not silently change with configuration.
- `metadata` is **not** echoed in the response. `/v1/systemone` remains a strict superset of
  Jev's response.

## Terminal display (`LAYA_DEBUG_REQUESTS=1`)

Off by default. When on, one readable multi-line block per `POST /v1/systemone`, emitted
through `logging.getLogger("tryout_laya.requests")` at `INFO` (so `LAYA_LOG_LEVEL` still
governs visibility) rather than `print`. `/health` and other paths are never logged.

```
[2026-10-01T12:34:56.789Z] POST /v1/systemone -> 200 in 412.3ms
  clientId=videosvc  model=english
  metadata: {"clientId": "videosvc", "timestamp": 12.5}
  state: "Put the oats in a blender, add the protein powder and berries."
  questions: {"isRecipe": {"type": "noul", "instructions": "..."}}
  routing: english (English Latin text)
  usage: input_tokens=164 output_tokens=0
  answers: isStory=0.12 isRecipe=0.93
```

- `model` is the checkpoint that answered (`routing.model`); `clientId` comes from metadata
  when valid.
- `answers` is a compact `name=value` summary (`choice`/`noul` show their value,
  `score` shows the score).
- On a non-200 response, print `status=<code> detail="<detail>"` instead of routing/usage/
  answers.
- Any serialized field longer than `LAYA_DEBUG_MAX_CHARS` (default `500`) is truncated and
  suffixed with `…(+N chars)`; this applies to `state`, `questions`, `metadata`, and the
  answers summary. The default keeps a 50k-character state from flooding the terminal.

## Storage

### Recorder interface

`recorder.py` defines:

```python
@dataclass(frozen=True)
class RequestRecord:
    recorded_at: str      # ISO-8601 UTC, millisecond precision, trailing "Z"
    client_id: str
    model: str | None
    content_hash: str
    metadata: str         # JSON text
    request: str          # JSON text
    response: str         # JSON text

class RequestRecorder(Protocol):
    def record(self, entry: RequestRecord) -> None: ...
    def close(self) -> None: ...
```

Only `SqliteRequestRecorder` ships. A different backend later is a new class behind the same
protocol.

### SQLite schema (created at startup)

```sql
CREATE TABLE IF NOT EXISTS requests (
    id           INTEGER PRIMARY KEY,
    recorded_at  TEXT    NOT NULL,   -- ISO-8601 UTC
    client_id    TEXT    NOT NULL,   -- metadata.clientId
    model        TEXT,               -- routing.model, NULL only if absent
    content_hash TEXT    NOT NULL,   -- sha256(canonical(state, questions))
    metadata     TEXT    NOT NULL,   -- full metadata object as JSON
    request      TEXT    NOT NULL,   -- full request body as JSON
    response     TEXT    NOT NULL    -- full response body as JSON
);
CREATE INDEX IF NOT EXISTS requests_client_time    ON requests(client_id, recorded_at);
CREATE INDEX IF NOT EXISTS requests_client_content ON requests(client_id, content_hash);
```

Connection settings: `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`,
`PRAGMA busy_timeout=5000`. The directory is created if missing.

`content_hash = sha256(json.dumps({"state": state, "questions": questions},
sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()`. It covers the input
only — not `model` — so a query can optionally add `model` to the `GROUP BY` when comparing
checkpoints on the same input.

`request`/`response`/`metadata` are stored with `json.dumps(..., ensure_ascii=False)`. There
is deliberately no `UNIQUE` constraint on `content_hash`: repeated requests are separate
rows, and the repetition count is the signal.

### Write path and failure behavior

- The recorder owns a single daemon writer thread and a `queue.Queue`. `record()` only
  enqueues and never blocks the event loop or the inference pool; the writer thread performs
  all SQLite I/O. `close()` drains and joins (called from app shutdown if practical; the
  thread is a daemon regardless).
- Writing to SQLite from the async middleware directly is forbidden — it would block the
  event loop.
- Any write error is logged as a warning and swallowed. A storage failure must never turn a
  successful inference into a 500 or change the response.
- Because storage is gated on `status == 200`, no failed inference is ever written.

### The dedup query this schema is designed for

```sql
-- repeated inputs per client
SELECT client_id, content_hash, COUNT(*) AS repeats,
       MIN(recorded_at) AS first_seen, MAX(recorded_at) AS last_seen
FROM requests GROUP BY client_id, content_hash HAVING repeats > 1;

-- distinct inputs per client
SELECT client_id, content_hash, COUNT(*) FROM requests GROUP BY client_id, content_hash;

-- representative (latest) row per distinct input
SELECT r.* FROM requests r JOIN (
  SELECT client_id, content_hash, MAX(id) AS id
  FROM requests GROUP BY client_id, content_hash
) latest ON r.id = latest.id;
```

Semantics to document for users: the hash is byte-exact after canonicalization, so
key-order and whitespace differences *inside string values* mean two inputs are treated as
different. That is the intended meaning of "the same request repeated".

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `LAYA_DEBUG_REQUESTS` | off | `1/true/yes/on` prints the per-request block |
| `LAYA_DEBUG_MAX_CHARS` | `500` | Truncation length for logged fields |
| `LAYA_REQUESTS_DB` | unset | Storage path. Unset/empty = storage off; `1/true/yes/on` = `.logs/requests.db`; any other value = that path |
| `LAYA_REQUESTS_DB=1` default path | `.logs/requests.db` | Relative to the process working directory |

All existing `LAYA_*` variables keep working; they are read by upstream.

## Files to change

- **Add** `tryout_laya/` (`__init__.py`, `config.py`, `observe.py`, `request_log.py`,
  `recorder.py`, `server.py`).
- **Add** `tests/test_observe.py`.
- **Edit** `Makefile`: `serve` target runs `uv run python -m tryout_laya.server`; keep
  passing the existing `LAYA_*` values inline; add `export LAYA_REQUESTS_DB
  LAYA_DEBUG_REQUESTS LAYA_DEBUG_MAX_CHARS` so values placed in `.env` reach the process
  (they are loaded by `-include .env`). No new make variable is introduced. Mention logs in
  `make help`.
- **Edit** `.gitignore`: add `.logs/`.
- **Edit** `.env.example`: document the three new variables, commented out / off by default.
- **Do not edit** `README.md` (workspace rule) or any file under
  `.venv/lib/python3.12/site-packages/laya/`.

## Tests

`tests/test_observe.py` uses a stub router (`predict()` returns a canned Jev-shaped dict,
`loaded` is a list) injected through `build_observed_app(router=stub)`, so it downloads
nothing and runs fast. `tests/test_server.py` is left unchanged as the real-checkpoint e2e
test.

Cases:

1. Metadata absent → `200`, response unchanged, no request log, no DB row (storage on).
2. Valid metadata + storage on → exactly one row; `client_id`, `model`, `content_hash`,
   `metadata`, `request`, `response` populated as specified.
3. Metadata present without `clientId` → `400`, `predict` never called, no row.
4. `clientId` empty, whitespace-only, or non-string → `400`, no row.
5. `metadata` present but not an object (e.g. a string/array) → `400`, no row.
6. Storage off (default) → valid metadata request returns `200` and creates no DB file.
7. Inference raises → `500`, no row.
8. Same `state`+`questions` twice plus one different → identical `content_hash` for the
   repeat pair; the dedup `GROUP BY` query returns the expected counts.
9. `LAYA_DEBUG_REQUESTS=1` → captured log contains `clientId` and the state; off → no
   request-log lines.
10. `GET /health` → never logged, never recorded.
11. Body over the 2 MB cap → `413`; inner app not called.
12. `metadata` invalid while storage is off → still `400` (contract is config-independent).

## Acceptance criteria

- `make test` passes (both the fast new tests and the existing real-checkpoint test).
- `make serve` starts the wrapper; `/health` is unchanged.
- A request without metadata behaves byte-for-byte as before.
- `LAYA_DEBUG_REQUESTS=1 make serve` prints one block per call, errors included.
- With `LAYA_REQUESTS_DB=.logs/requests.db`, a metadata-bearing `200` appears in
  `.logs/requests.db`; a request without metadata, a `400`, and a failed inference do not.
- Both dedup queries return the expected rows for repeated inputs.
- No block is added to the event loop or inference path: logging is non-blocking and SQLite
  writes happen on a dedicated writer thread.

## Open questions / future work

- Retention and pruning (currently manual).
- A read/query surface (CLI or endpoint) if the `sqlite3` CLI proves insufficient.
- Additional recorder backends behind the existing protocol.
- Near-duplicate detection (whitespace/wording-insensitive) if byte-exact input equality
  proves too strict for evaluation.
