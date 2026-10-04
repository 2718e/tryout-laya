# Relative line position vs assigned probability

Date: 2026-10-04

## What it does

`make eval` reads the exchanges saved by the request observer and tests the hunch
that later lines in a `choice` question get lower probabilities. For every saved
choice answer it rewrites each line label as its offset from the lowest label in the
excerpt (`L071`..`L110` becomes `0`..`39`), averages the probabilities per relative
position across requests, and reports the correlation between the two series. It
prints the raw averages and writes a graph.

## Usage

```bash
make eval
# or, with explicit paths
uv run python -m src.eval --db .logs/requests.db --output /tmp/graph.png
```

`--db` defaults to `.logs/requests.db`, `--output` to
`src/eval/output/position_probability.png`, and `--lines` to `40`. `--lines` is the
number of labelled lines a request must have (plus a `none` option) to be used;
requests with any other count are counted as excluded.

## Method

Only `choice` questions with exactly `--lines` labels matching `L<digits>` and a
`none` criterion are used, and only when the answer carries a probability for every
label. `none` is reported separately because it is not a line.

The pooled series (one mean per relative position) is correlated with the position
numbers two ways:

- **Pearson** — linear association.
- **Spearman** — monotone association, on ranks.

Both get a permutation p-value (10,000 shuffles, fixed seed): because the position
series has one value per line and is far from normal, a permutation test is safer
than the normal-theory p-value.

A **per-request Spearman** coefficient is also reported. It asks the same question
inside a single response, where the probabilities sum to one, so it is not distorted
by how peaked individual responses are. Its p-value is an exact two-sided sign test.

## Result on the current database

27 of 57 records qualify. The effect is real and consistent:

| Statistic | Value |
| --- | --- |
| Pearson r (position vs mean probability) | -0.536 (permutation p = 0.0001) |
| Spearman rho | -0.789 (permutation p = 0.0001) |
| Linear fit | mean = -0.001517·position + 0.043627, R² = 0.287 |
| Per-request Spearman | mean -0.678, median -0.694, **27 / 27 negative** (sign-test p ≈ 1.5e-8) |
| Mean `none` probability | 0.438 |

Position 0 carries a mean probability of 0.191; the mean falls below 0.002 by
position 14 and stays there. The linear fit is weak (R² 0.287) because the decline is
not linear — it is a drop-off concentrated in the first ~13 positions — which is why
Spearman is much stronger than Pearson. Every one of the 27 requests shows the same
direction on its own, so the hunch holds.

## Where it lives

- `src/eval/dataset.py` — reads SQLite, filters, rewrites labels to relative positions.
- `src/eval/statistics.py` — per-position averages, Pearson/Spearman with permutation
  p-values, per-request Spearman with a sign test, linear fit.
- `src/eval/plot.py` — the graph (linear and log panels, standard-error bars).
- `src/eval/__main__.py` — CLI and console report, run as `python -m src.eval`.
- `tests/test_eval.py` — synthetic-exchange tests for the filter and statistics.

## Refactor

As part of this work the service package was renamed `tryout_laya/` → `src/`. Imports
are now `src.*`, `make serve` runs `python -m src.server`, and the request logger is
`src.requests`. The feature docs and refined specs predating this keep the old paths
as a record of the state at the time.
