"""Download the Laya checkpoints into HF_HOME before serving.

`laya-serve` downloads on first use anyway; this only moves that wait out of the
first request. Run it through `make fetch` so HF_HOME points at the project cache.
"""
import os

from huggingface_hub import snapshot_download

# Every checkpoint comes from convaiinnovations/laya: the English weights are the
# repo root, the other two are subfolders. None means the root.
CHECKPOINTS = {
    "english": None,
    "multilingual": "multilingual",
    "typed-decisions": "typed-decisions",
}


def main() -> None:
    wanted = [name.strip() for name in os.environ.get("MODELS", "").split(",") if name.strip()]
    unknown = sorted(set(wanted) - set(CHECKPOINTS))
    if unknown:
        raise SystemExit(f"unknown checkpoint(s): {', '.join(unknown)}")

    for name in wanted or CHECKPOINTS:
        print(f"fetching {name}", flush=True)
        snapshot_download("convaiinnovations/laya", subfolder=CHECKPOINTS[name])

    print(f"checkpoints cached in {os.environ.get('HF_HOME', 'the default Hugging Face cache')}")


if __name__ == "__main__":
    main()
