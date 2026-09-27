# GPU support: running on a GTX 1070 (Pascal)

## The problem

`torch` resolved from PyPI by default was **2.14.0+cu130**. That build bundles the CUDA 13
runtime, which requires an NVIDIA driver of 580 or newer. On a driver reporting `12040`
(CUDA 12.4) torch cannot initialise CUDA at all:

```
UserWarning: CUDA initialization: The NVIDIA driver on your system is too old (found version 12040)
```

Torch then silently falls back to CPU, so the warning is easy to miss.

The driver, not Laya, is the constraint. Nothing in Laya needs a recent torch: it declares
`torch>=2.0.0`, has no version gates, and the API surface it uses (`torch.compile`,
`torch.autocast`, `torch.inference_mode`, `torch.utils.checkpoint`, `nn.functional`)
predates 2.0 in every case that matters.

## What the project now pins

| | Before | Now |
| --- | --- | --- |
| torch | 2.14.0+cu130 (PyPI) | 2.6.0+cu124 (PyTorch index) |
| CUDA runtime | 13.0 | 12.4 |
| nvidia wheels | `*-cu13` | `*-cu12` |
| cuDNN | 9.24 | 9.1 |
| Compatible driver | 580+ | 525+ (any CUDA 12.x) |

CUDA has *minor version compatibility*: a CUDA 12.x runtime works on any driver that
supports CUDA 12.0, so a cu124 build runs on the 12.4 driver rather than demanding the exact
matching version.

## Why torch 2.6 and not something newer

Pascal support is what pins the version, not the driver. PyTorch compiles each wheel for a
fixed architecture list, and Pascal drops out of it at 2.7:

| torch | Architectures compiled into the CUDA wheels | GTX 1070 (sm_61) |
| --- | --- | --- |
| 2.6.0 | `sm_50 sm_60 sm_70 sm_75 sm_80 sm_86 sm_90` | works |
| 2.7.0+ | `sm_70 sm_75 sm_80 sm_86 sm_90 sm_100 sm_120` | no |

`sm_61` is never listed for 2.6 either, but that is not a problem: the GTX 1070 runs the
`sm_60` cubins, because SASS is forward-compatible within a major compute capability.
Verified by listing the embedded kernels directly:

```bash
cuobjdump --list-elf .venv-agent-container/lib/python3.12/site-packages/torch/lib/libtorch_cuda.so
# sm_50 sm_60 sm_70 sm_75 sm_80 sm_86 sm_90
```

So `>=2.6,<2.7` is not an arbitrary pin — it is the newest torch that still carries Pascal
kernels. 2.6.0 is also the newest release on the cu124 index.

## How it is configured

In `pyproject.toml`:

```toml
dependencies = ["laya==0.3.20", "torch>=2.6,<2.7"]

[[tool.uv.index]]
name = "pytorch-cu124"
url = "https://download.pytorch.org/whl/cu124"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cu124" }
```

Two things here are load-bearing and easy to get wrong:

1. **`torch` must be a direct dependency.** `[tool.uv.sources]` is ignored for transitive
   dependencies, and torch arrives through `laya`. Selecting the index only works because
   torch is named explicitly in `dependencies`.
2. **There must be no `uv.toml`.** uv ignores `[tool.uv]` in `pyproject.toml` when a
   `uv.toml` sits beside it (it warns, but continues). The uv cache setting used to live in
   `uv.toml`; it is now `cache-dir` under `[tool.uv]`, so the project has one config file
   and the index setting actually applies.

`torch-backend = "cu124"` was tried and does **not** work here: uv documents it as
respected only by `uv pip` commands, and `uv lock`/`uv sync` silently ignore it.

## Reverting to CPU-only

If the GPU is not worth it, replace the `torch` source with the CPU index:

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
```

and drop the `<2.7` upper bound, which exists only for Pascal. Then `uv lock && uv sync`.

Moving to a newer NVIDIA card means changing the index URL (`cu126`, `cu128`, ...) and
dropping the upper bound.

## Consequences to keep in mind

- **Fine-tuning will be capped at torch 2.6.** That is the real cost of this pin, and it is
  what the README's fine-tuning notes were worried about: training stacks (`peft`, `trl`,
  `datasets`) move quickly and some already expect torch 2.7+. A GTX 1070 has 8 GB and is
  weak at training, so training may belong on a rented GPU with a modern stack while serving
  stays on Pascal here.
- **No bfloat16.** Pascal has no native bf16, so training must use fp16 or fp32.
- **Slower than the published numbers.** The model card's latency figures are from a Tesla
  T4. A GTX 1070 is older and slower, so expect more than the quoted 32.8 ms per question,
  though still comfortably ahead of CPU.
- **`/health`'s `device` field is not the resolved device.** `laya-serve` echoes the
  `LAYA_DEVICE` string back verbatim, so it reads `"cuda"` even when torch has quietly
  fallen back to CPU. Confirm the real device with:

  ```bash
  uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
  ```

  Expect `2.6.0+cu124 True` on the host. If it prints `False`, torch could not initialise
  CUDA and the run is on CPU whatever `/health` says.
- **The `CUDA initialization` warning should now be gone.** If it persists on the host,
  check the driver with `nvidia-smi` and the command above.

## Verification

Resolution and CPU behaviour were verified here, but the container has no GPU, so the CUDA
path itself can only be confirmed on the host.

- `uv lock` resolves `torch==2.6.0+cu124` from `download.pytorch.org/whl/cu124` with
  `nvidia-*-cu12` dependencies.
- The isolated-install check confirmed `laya 0.3.20` + `transformers 5.17.0` + `torch 2.6.0`
  predict correctly on CPU (transformers only requires `torch>=2.5`).
- `make test` passes on the pinned stack in the project environment.
- `cuobjdump` confirms the `sm_60` cubins that cover the GTX 1070 are present in the wheel.
