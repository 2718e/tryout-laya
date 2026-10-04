# Laya decision engine over HTTP. See README.md for the full walkthrough.
#
# Every setting has a default, so `make serve` works with no configuration.
# Override on the command line (`make serve PORT=9000`) or in .env.

-include .env

HOST       ?= 127.0.0.1
PORT       ?= 8000
DEVICE     ?= cpu
MODELS     ?= english,multilingual,typed-decisions
PRELOAD    ?= 1
THREADS    ?= 8
LAYA_API_KEY ?=

# The server reads LAYA_API_KEY from the environment and treats an empty value as
# "no authentication", which is the intended localhost default.
export LAYA_API_KEY

# Loaded by -include .env above, so they must be exported to reach the process.
# Empty values mean "no request logging" and "no request storage".
export LAYA_REQUESTS_DB LAYA_DEBUG_REQUESTS LAYA_DEBUG_MAX_CHARS

UV     := uv
HF_HOME ?= $(CURDIR)/.cache/huggingface
export HF_HOME

UV_FLAGS := --all-extras --group dev

.PHONY: help install serve test eval fetch clean

help:
	@echo "install  resolve and install dependencies into .venv-agent-container"
	@echo "fetch    download the checkpoints into $(HF_HOME)"
	@echo "serve    run the HTTP server on http://$(HOST):$(PORT)"
	@echo "test     pytest (the smoke test loads a checkpoint on first run)"
	@echo "eval     analyse LAYA_REQUESTS_DB and graph probability by line position"
	@echo "clean    drop the local model cache and uv cache"
	@echo ""
	@echo "Request logs: LAYA_DEBUG_REQUESTS=1 prints each request, and"
	@echo "LAYA_REQUESTS_DB=.logs/requests.db stores metadata-bearing requests."

install:
	$(UV) sync $(UV_FLAGS)

fetch: install
	$(UV) run python scripts/fetch_models.py

# DEVICE is always passed explicitly. The server treats an absent device as
# "auto-detect", but the literal string "auto" is not a torch device and aborts
# startup, so cpu/cuda/mps are the only useful values here.
serve: install
	LAYA_HOST=$(HOST) LAYA_PORT=$(PORT) LAYA_DEVICE=$(DEVICE) \
	LAYA_MODELS=$(MODELS) LAYA_PRELOAD=$(PRELOAD) LAYA_THREADS=$(THREADS) \
	LAYA_API_KEY=$(LAYA_API_KEY) \
	$(UV) run python -m src.server

test: install
	$(UV) run pytest

eval: install
	$(UV) run python -m src.eval

clean:
	rm -rf .cache/huggingface .uv-cache
