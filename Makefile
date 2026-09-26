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

UV     := uv
HF_HOME ?= $(CURDIR)/.cache/huggingface
export HF_HOME

UV_FLAGS := --all-extras --group dev

.PHONY: help install serve test fetch clean

help:
	@echo "install  resolve and install dependencies into .venv-agent-container"
	@echo "fetch    download the checkpoints into $(HF_HOME)"
	@echo "serve    run the HTTP server on http://$(HOST):$(PORT)"
	@echo "test     pytest (the smoke test loads a checkpoint on first run)"
	@echo "clean    drop the local model cache and uv cache"

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
	$(UV) run laya-serve

test: install
	$(UV) run pytest

clean:
	rm -rf .cache/huggingface .uv-cache
