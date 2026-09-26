# tryout-laya

A local HTTP service for [Laya](https://huggingface.co/convaiinnovations/laya), a
non-autoregressive System 1 decision model. Send it a state (text, email, ticket, or JSON)
plus typed questions, and it returns typed answers with calibrated probabilities from a
single forward pass. It never generates text, so there is nothing to parse and nothing to
hallucinate.

The service speaks TypeSafe Jev's `POST /v1/systemone` protocol, so anything already
written against Jev works by changing its base URL to this one.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.12 (uv downloads it if you do not have it)

Python is pinned to 3.12 in `pyproject.toml` because `torch` ships no 3.13 wheels yet.

## Setup

```bash
uv sync --all-extras --group dev
```

That creates `.venv-agent-container/` and installs Laya plus the HTTP server extras. The
environment directory is deliberately not `.venv`, so it can never collide with a host
virtualenv. Nothing is installed system-wide.

The first request downloads a checkpoint (roughly 800 MB for the English one, 2.3 GB for
all three). To get that wait out of the way up front:

```bash
make fetch
```

Expect the environment itself to be several GB: PyPI's default `torch` build pulls the CUDA
runtime, which is unused on a CPU-only host. If disk matters, install torch from the
CPU-only index instead and re-lock.

## Run

```bash
make serve
```

The server binds `127.0.0.1:8000`. Checkpoints are preloaded by default, so the first
request is already fast.

```bash
curl -s localhost:8000/health
# {"status":"ok","loaded":["english","multilingual","typed-decisions"],"device":"cpu"}
```

Make a decision:

```bash
curl -s localhost:8000/v1/systemone -H 'Content-Type: application/json' -d '{
  "state": "Hi, we were billed twice for March. Please refund the duplicate today or we will cancel our plan.",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which department should handle this?",
      "criteria": {
        "billing": "invoices, payments, refunds",
        "technical": "bugs, outages, system errors",
        "other": "everything else"
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this?",
      "criteria": ["not urgent", "soon", "blocking"]
    },
    "churn_risk": {
      "type": "noul",
      "instructions": "Does the user threaten to cancel or leave?"
    }
  }
}'
```

```json
{
  "model": "laya-rl-agent",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "billing",
      "probabilities": {"billing": 0.9865, "technical": 0.008, "other": 0.0055},
      "confidence": 0.9267,
      "answer_confidence": 0.9865,
      "action": {"act_probability": 1.0}
    },
    "urgency": {
      "type": "score",
      "score": 1.7722,
      "legend": {"0": "not urgent", "1": "soon", "2": "blocking"},
      "probabilities": {"0": 0.0389, "1": 0.15, "2": 0.8111},
      "confidence": 0.4714,
      "answer_confidence": 0.8111,
      "action": {"act_probability": 1.0}
    },
    "churn_risk": {
      "type": "noul",
      "noul": 0.879,
      "confidence": 0.879,
      "answer_confidence": 0.879,
      "action": {"act_probability": 1.0}
    }
  },
  "usage": {"input_tokens": 164, "output_tokens": 0},
  "routing": {
    "model": "english",
    "repo": "convaiinnovations/laya",
    "reason": "English Latin text",
    "workflow": null
  }
}
```

Every question gives a `choice` (with the full `probabilities` map), `score`, or `noul`
answer, plus a `confidence`, and `routing` says which checkpoint answered and why. When you
send `"model": "typed-decisions"`, that checkpoint is used and `routing.model` reflects it.

The three question types are `choice` (pick one of `criteria`), `score` (an ordinal
position across `criteria`), and `noul` (a yes/no probability). `state` may also be an
object, for example an email with `from`, `subject`, and `body`; the model reads the whole
JSON.

The server answers `GET /health`, returns 422 with a readable message for a malformed
question, and 401 when `LAYA_API_KEY` is set and the bearer token does not match.

Full output is a superset of Jev's: `answers` and `usage` decode the same way, and `routing`
is extra. Two documented fields are not worth trusting yet: `action.act_probability` reads
1.0 for nearly every input, and `noul` on the English checkpoint sometimes follows its own
`false`/`true` labels instead of the state. Gate on `confidence`, and read the model card's
"Honest Limits" before relying on any single primitive.

## Configuration

Every setting has a working default. Override any of them on the command line or in a
`.env` file (copy `.env.example` to start one; it is gitignored).

| Make variable | Server env var | Default | Meaning |
| --- | --- | --- | --- |
| `HOST` | `LAYA_HOST` | `127.0.0.1` | Bind address; use `0.0.0.0` to reach it from your LAN |
| `PORT` | `LAYA_PORT` | `8000` | Bind port |
| `DEVICE` | `LAYA_DEVICE` | `cpu` | `cpu`, `cuda`, or `mps`. Setting it empty is not useful; the server reports whatever you pass |
| `MODELS` | `LAYA_MODELS` | all three | Checkpoints to keep resident |
| `PRELOAD` | `LAYA_PRELOAD` | `1` | Load checkpoints at startup instead of on first use |
| `THREADS` | `LAYA_THREADS` | `8` | torch intra-op threads; do not exceed physical cores |
| — | `LAYA_AUTO_TASK` | `0` | Let auto-routing also reach `typed-decisions` |
| `LAYA_API_KEY` | `LAYA_API_KEY` | unset | When set, require `Authorization: Bearer <key>` |
| `HF_HOME` | `HF_HOME` | `.cache/huggingface` | Where checkpoints are cached |

```bash
make serve PORT=9000 DEVICE=cuda
```

### Checkpoints

Auto-routing only ever chooses between `english` and `multilingual`; `typed-decisions` is
reached by naming it in the request (`"model": "typed-decisions"`) or by running with
`LAYA_AUTO_TASK=1`. Holding all three resident costs roughly 1.2B parameters of memory, so
drop `typed-decisions` from `MODELS` if you do not need it:

```bash
make serve MODELS=english,multilingual
```

## Using it from another program

Any HTTP client works. Point a Jev client's base URL at
`http://127.0.0.1:8000` and keep its request shape.

For Python code in another project, the wire protocol is plain JSON, so the standard
library is enough:

```python
import urllib.request, json

request = urllib.request.Request(
    "http://127.0.0.1:8000/v1/systemone",
    data=json.dumps({
        "state": "I was charged twice. Please fix this ASAP.",
        "questions": {"billing": {"type": "noul", "instructions": "Is this about billing?"}},
    }).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request) as response:
    print(json.load(response)["answers"])
```

Within this project, `laya.Router` can also be called in-process, which skips HTTP entirely
but holds the models in the calling process.

## Tests

```bash
make test
```

`tests/test_server.py` drives the served HTTP surface end to end against a real checkpoint,
so the first run downloads weights and needs network access. It runs on CPU.

## Layout

```
.
├── Makefile            install / fetch / serve / test / clean
├── pyproject.toml      Python 3.12, pinned laya, serve and dev extras
├── uv.toml             sends uv's cache to .uv-cache
├── .env.example        server settings to copy into a gitignored .env
├── scripts/
│   └── fetch_models.py predownload the checkpoints into HF_HOME
└── tests/
    └── test_server.py  end-to-end test over the HTTP API
```

`uv.lock` is committed, so `uv sync` resolves the exact versions this project was tested
with.

## Fine-tuning later

The zero-shot checkpoints are a fast base to specialise, not a finished decision engine:
on the typed-decisions benchmark the base English checkpoint scores 0.362, while the
fine-tuned `laya-typed-decisions` checkpoint scores 0.766. If you fine-tune, this project is
laid out to absorb it:

- Fine-tuning wants a GPU and a heavier dependency set (datasets, accelerate, tracking).
  Add them as a separate optional extra so `uv sync --all-extras` for serving stays small,
  and keep training code out of the serving path.
- `Router` takes a checkpoint map and `Agent` accepts a local directory wherever it accepts
  a Hub id, so a fine-tuned checkpoint drops in by overriding one of the three names. The
  server reads its checkpoints from the environment, so this is the one case that needs a
  couple of lines of Python rather than a `make` variable:

  ```python
  import uvicorn, laya
  from laya.serve import create_app

  router = laya.Router(models={"english": "./checkpoints/my-finetune"}, preload=True)
  uvicorn.run(create_app(router), host="127.0.0.1", port=8000)
  ```

  `Router` only understands the existing shape, so a new checkpoint must replace one of the
  names defined at construction.
- Add a `training/` directory beside `scripts/` when you get there; nothing in the current
  layout assumes serving is the only thing this project will do.

Note that Laya's probabilities ship over-confident. The model card reports one temperature
per (question type, option count) moving mean ECE from 0.466 to 0.081. Fit that on your own
data before trusting the numbers.
