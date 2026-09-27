# 2026-09-26 — tryout-laya service project

## What this is

A `uv`-managed project that runs [Laya](https://huggingface.co/convaiinnovations/laya)
(`laya==0.3.20`) as a local HTTP decision engine, so other programs can call
`http://127.0.0.1:8000/v1/systemone` for typed decisions with calibrated probabilities.

## Decisions worth knowing

**No server code of our own.** Laya already ships `laya-serve`
(`laya/serve.py`), which exposes the `Router` over TypeSafe Jev's
`POST /v1/systemone` protocol, with `GET /health`, a bearer check, and request-size
guards. Re-implementing it would only add drift, so the project's job is configuration:
Makefile targets, a pinned lockfile, and a local model cache.

**Python pinned to `==3.12.*`.** `laya` allows `>=3.10`, and its own classifiers claim
3.13, but `torch` publishes no cp313 wheels, so a 3.13 environment cannot resolve torch at
all. Pin 3.12 in `pyproject.toml` and let uv download the interpreter.

**`.venv-agent-container` is untouched; `.venv` is never created.** Per the workspace
global instructions the host owns `.venv`. uv's `.venv` default is overridden by the
container's `UV_PROJECT_ENVIRONMENT`. `[tool.uv] package = false` keeps uv from trying to
build this directory as a package.

**Cache paths had to move into the project.** The container's `$HOME` is read-only, so
uv's default cache (`~/.cache/uv`) and managed-interpreter dir (`~/.local/share/uv/python`)
both fail with `Permission denied`:

- `uv.toml` sets `cache-dir = ".uv-cache"` (uv rejects it under `[tool.uv]` in
  `pyproject.toml`).
- `.envrc` exports `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` for the container run.
  These are container-only overrides and are not needed on the host.
- `HF_HOME` defaults to `<project>/.cache/huggingface` via the Makefile, so ~1.2 GB of
  checkpoints land in the project rather than in a home directory.

**Three checkpoints, one repo.** `english` is the root of `convaiinnovations/laya`;
`multilingual` and `typed-decisions` are subfolders of the same repo, so all weights come
from one `snapshot_download` with `subfolder=`. All three are preloaded by default
(`LAYA_PRELOAD=1`, ~2.3 GB on disk); auto-routing only ever picks between english and
multilingual, and `typed-decisions` is reached by naming it in the request or setting
`LAYA_AUTO_TASK=1`. `LAYA_THREADS=8` is set because oversubscribing logical cores is a
throughput regression on CPU.

**`DEVICE` defaults to `cpu`, not `auto`.** `build_router` passes `LAYA_DEVICE` straight to
`Agent`, which calls `torch.device(...)`: the literal string `auto` raises `RuntimeError` at
startup, and auto-detection only happens when the variable is absent. Rather than smuggle an
empty value through `make`, the Makefile always passes an explicit device, which also makes
`/health` report the truth instead of `"auto"`. An earlier attempt at defaulting `HOST` to
`0.0.0.0` was also dropped: localhost is the stated use case and the unauthenticated default
should not be reachable from the LAN by accident.

**The server reads `LAYA_MODELS` as names only**, validated against `Router.DEFAULT_MODELS`,
so a fine-tuned checkpoint cannot be served by pointing an env var at a local directory. The
documented path is two lines of Python building a `Router` with an overridden model map and
passing it to `create_app`. This is the one seam where a future fine-tune needs code.

**Running `uv run laya-serve` directly fails in this container** unless `HF_HOME` is set: the
default Hugging Face cache is under the read-only `$HOME`, so the checkpoint re-download
cannot be written and inference returns 500. The Makefile exports `HF_HOME`, which is why
`make serve` is the documented entry point. On a host with a writable `$HOME` this does not
bite.

**torch is pinned to the CUDA 12.4 build for a GTX 1070.** The initial lock took
`torch==2.14.0+cu130` from PyPI, which needs a 580+ driver; the host reports `12040`
(CUDA 12.4), so CUDA initialisation failed and torch fell back to CPU. The project now pins
`torch>=2.6,<2.7` from `https://download.pytorch.org/whl/cu124`, giving `2.6.0+cu124` and
`nvidia-*-cu12` wheels. The upper bound is not arbitrary: 2.6 is the last release whose CUDA
wheels carry Pascal cubins (`sm_50 sm_60 ...`, verified with `cuobjdump`), and 2.7+ drops
everything below `sm_70`. The GTX 1070 is `sm_61`, which runs the `sm_60` cubins because SASS
is forward-compatible within a major compute capability. Full write-up in
`docs/gpu-support.md`.

Two uv behaviours cost time here and are worth remembering:

1. `[tool.uv.sources]` is ignored for **transitive** dependencies. Torch arrives through
   `laya`, so the index override only took effect once `torch` was named as a direct
   dependency.
2. uv ignores `[tool.uv]` in `pyproject.toml` when a `uv.toml` exists beside it. The cache
   setting was living in `uv.toml`, which silently disabled the new index config. `uv.toml`
   is deleted and `cache-dir` now sits under `[tool.uv]` alongside everything else.

`torch-backend = "cu124"` was also tried and does not work for this project: uv documents it
as respected only by `uv pip` commands, and `uv lock`/`uv sync` ignore it silently.

**`transformers` resolved to 5.17.0**, a major version above the `>=4.48.0` floor that
`laya` declares. Verified working end to end on 0.3.20, and again on the 2.6.0 downgrade,
before committing to it.

The user rewrote the root `README.md` as their own experimentation notes, so the GPU
documentation went to `docs/gpu-support.md` instead. The global instruction not to modify
the root README stands.

## Fine-tuning readiness

Serving and training are kept separable: no training dependency is in the core group, and
the README records that fine-tuning should arrive as a separate optional extra plus a
`training/` directory. `Router` accepts a local directory wherever it accepts a Hub id, so
a fine-tuned checkpoint drops in without server changes.

The Pascal pin is the main cost to training: it caps torch at 2.6, and some training stacks
already expect 2.7+. Training on a rented GPU with a modern stack while serving on the 1070
is the likely split. Pascal also has no bfloat16, so training must use fp16 or fp32.

## Verification

- `uv sync --all-extras --group dev` resolves and installs; `make test` passes in a clean
  shell without any manual environment setup, including after the torch 2.6 downgrade.
- `tests/test_server.py` boots the FastAPI app through `TestClient`, loads the English
  checkpoint, and asserts a real `noul` probability over the HTTP route, plus health and 422
  paths.
- `make serve` was run for real and checked with curl: `/health` reports all three
  checkpoints loaded; the billing request returns `billing` / 1.7722 / 0.879; a Hindi state
  routes to `multilingual`; `"model": "laya-typed-decisions"` routes to `typed-decisions`; a
  malformed question type returns 422 with a readable message; and with `LAYA_API_KEY` set, a
  missing or wrong bearer token returns 401.
- The torch downgrade was validated beyond resolution: a throwaway environment with
  `torch 2.6.0` + `laya 0.3.20` + `transformers 5.17.0` ran a real prediction correctly, and
  `cuobjdump` confirmed the Pascal cubins are present in the wheel.
- `make test` emits a `RuntimeWarning` from `laya/router.py` that the shipped checkpoint
  temperatures are invalid and are clamped, which is the model card's over-confidence
  caveat showing up in practice.
- The container has no GPU, so the CUDA path itself is unverified; the host is the only
  place it can be confirmed. `/health`'s `device` field is not evidence, because it echoes
  the configured string rather than the device torch resolved.
