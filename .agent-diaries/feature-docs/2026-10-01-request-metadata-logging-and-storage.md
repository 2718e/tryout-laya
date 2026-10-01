# Request metadata, terminal visibility, and request storage

Date: 2026-10-01

## What it does

`make serve` now runs a small wrapper instead of `laya-serve` directly. The wrapper
adds three things to the Laya HTTP service without touching upstream `laya`:

- **Terminal visibility** — each `POST /v1/systemone` exchange can be printed.
- **Metadata passthrough** — callers may attach an arbitrary JSON `metadata` object.
- **Request storage** — requests carrying a valid `metadata.clientId` are persisted to
  SQLite for later evaluation.

`laya-serve` is still installed and unchanged, so it remains a working escape hatch.

## Usage

```bash
make serve                                    # same behaviour as before
LAYA_DEBUG_REQUESTS=1 make serve              # print each request/response
LAYA_REQUESTS_DB=.logs/requests.db make serve # store metadata-bearing requests
```

Configuration lives in the environment (and therefore in `.env`, which `make` exports):

| Env var | Default | Meaning |
| --- | --- | --- |
| `LAYA_DEBUG_REQUESTS` | off | `1/true/yes/on` prints the per-request block |
| `LAYA_DEBUG_MAX_CHARS` | `500` | Truncation length for logged fields |
| `LAYA_REQUESTS_DB` | unset | Storage path; `1` means `.logs/requests.db` |

## Metadata

`metadata` is optional and ignored by upstream. When present it must be a JSON object
with a non-empty string `clientId`; every other key is unvalidated. The contract is
enforced whether or not storage is on, and `metadata` is never echoed back. A request
without metadata behaves exactly as before.

## Request log

When `LAYA_DEBUG_REQUESTS=1`, one block per `/v1/systemone` call is emitted on the
`tryout_laya.requests` logger at `INFO` (so `LAYA_LOG_LEVEL` still gates it). The block
shows the status and timing, `clientId`/`model`, then the metadata, state, questions,
routing, usage, and a compact answers summary. On a non-200 it shows
`status=<code> detail="..."` instead. Long fields are truncated at
`LAYA_DEBUG_MAX_CHARS`. `/health` and other paths are never logged.

## Storage

Records are written by a single daemon writer thread fed by a `queue.Queue`, so SQLite
I/O never blocks the event loop or the inference pool. A failed write is logged and
swallowed. Only a `200` response with valid metadata is stored.

The schema is created at startup in the `requests` table (`id`, `recorded_at`,
`client_id`, `model`, `content_hash`, `metadata`, `request`, `response`) with indexes on
`(client_id, recorded_at)` and `(client_id, content_hash)`. `content_hash` is
`sha256` of the canonicalized `state` + `questions`; it deliberately has no `UNIQUE`
constraint, because repeated requests are separate rows and the repetition count is the
signal.

Inspect with the `sqlite3` CLI:

```sql
-- repeated inputs per client
SELECT client_id, content_hash, COUNT(*) AS repeats,
       MIN(recorded_at) AS first_seen, MAX(recorded_at) AS last_seen
FROM requests GROUP BY client_id, content_hash HAVING repeats > 1;

-- representative (latest) row per distinct input
SELECT r.* FROM requests r JOIN (
  SELECT client_id, content_hash, MAX(id) AS id
  FROM requests GROUP BY client_id, content_hash
) latest ON r.id = latest.id;
```

The hash is byte-exact after canonicalization, so key-order or whitespace differences
*inside string values* count as different inputs.

## Where it lives

- `tryout_laya/config.py` — env → `ObserverConfig`.
- `tryout_laya/observe.py` — pure-ASGI `RequestObserverMiddleware`.
- `tryout_laya/request_log.py` — terminal block formatting.
- `tryout_laya/recorder.py` — `RequestRecord`, recorder protocol, SQLite recorder.
- `tryout_laya/server.py` — `build_observed_app()` and the `python -m` entry point.
- `tests/test_observe.py` — fast tests with a stub router (no checkpoint load).
