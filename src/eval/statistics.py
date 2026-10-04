"""Average probability per relative line position, and its relation to position.

The headline statistic is the pooled view: the probability assigned to each
relative position is averaged over requests, and that series is correlated with
the position numbers. A permutation test supplies the p-value, because the
position series is small (one value per line) and its shape is not normal.

A per-request Spearman coefficient is reported alongside it. It asks the same
question inside a single response, where the probabilities sum to one, so it is
not distorted by differences in how peaked individual responses are.
"""
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

PERMUTATIONS = 10_000
SEED = 20_261_004


@dataclass(frozen=True)
class PositionMeans:
    positions: np.ndarray
    means: np.ndarray
    standard_deviations: np.ndarray
    counts: np.ndarray
    none_mean: float
    observation_count: int


@dataclass(frozen=True)
class Correlation:
    method: str
    coefficient: float
    p_value: float


@dataclass(frozen=True)
class PerRequestCorrelation:
    coefficients: np.ndarray
    mean: float
    median: float
    negative: int
    positive: int
    p_value: float


def average_by_position(observations) -> PositionMeans:
    per_position = defaultdict(list)
    for observation in observations:
        for position, probability in zip(observation.positions, observation.probabilities):
            per_position[position].append(probability)

    positions = np.array(sorted(per_position), dtype=float)
    samples = [np.array(per_position[int(position)], dtype=float) for position in positions]
    none_mean = float(np.mean([o.none_probability for o in observations])) if observations else math.nan
    return PositionMeans(
        positions=positions,
        means=np.array([sample.mean() for sample in samples]),
        standard_deviations=np.array(
            [sample.std(ddof=1) if sample.size > 1 else 0.0 for sample in samples]),
        counts=np.array([sample.size for sample in samples]),
        none_mean=none_mean,
        observation_count=len(observations),
    )


def correlations(position_means: PositionMeans, *,
                 permutations: int = PERMUTATIONS, seed: int = SEED) -> list[Correlation]:
    positions = position_means.positions
    means = position_means.means
    if positions.size < 3 or np.all(means == means[0]):
        return [Correlation(name, math.nan, math.nan)
                for name in ("pearson", "spearman")]

    rank_positions = _ranks(positions)
    observed = {
        "pearson": _pearson(positions, means),
        "spearman": _pearson(rank_positions, _ranks(means)),
    }

    rng = np.random.default_rng(seed)
    permuted = {name: np.empty(permutations) for name in observed}
    for index in range(permutations):
        shuffled = rng.permutation(means)
        permuted["pearson"][index] = _pearson(positions, shuffled)
        permuted["spearman"][index] = _pearson(rank_positions, _ranks(shuffled))

    return [Correlation(name, observed[name], _two_sided_p(observed[name], permuted[name]))
            for name in ("pearson", "spearman")]


def per_request_correlations(observations) -> PerRequestCorrelation:
    coefficients = np.array([
        _pearson(_ranks(o.positions), _ranks(o.probabilities)) for o in observations
    ])
    coefficients = coefficients[~np.isnan(coefficients)]
    negative = int(np.count_nonzero(coefficients < 0))
    positive = int(np.count_nonzero(coefficients > 0))
    return PerRequestCorrelation(
        coefficients=coefficients,
        mean=float(coefficients.mean()) if coefficients.size else math.nan,
        median=float(np.median(coefficients)) if coefficients.size else math.nan,
        negative=negative,
        positive=positive,
        p_value=_sign_test_p(negative, positive),
    )


def linear_fit(position_means: PositionMeans) -> tuple[float, float, float]:
    """Least-squares ``mean = slope * position + intercept`` and its R²."""
    positions = position_means.positions
    means = position_means.means
    slope, intercept = np.polyfit(positions, means, 1)
    residual = float(np.sum((means - (slope * positions + intercept)) ** 2))
    total = float(np.sum((means - means.mean()) ** 2))
    r_squared = 1.0 - residual / total if total else math.nan
    return float(slope), float(intercept), r_squared


def _pearson(x, y) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 2 or np.std(x) == 0 or np.std(y) == 0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def _ranks(values) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=float)
    ranks[order] = np.arange(values.size, dtype=float)
    sorted_values = values[order]

    start = 0
    while start < values.size:
        end = start
        while end + 1 < values.size and sorted_values[end + 1] == sorted_values[start]:
            end += 1
        if end > start:
            ranks[order[start:end + 1]] = (start + end) / 2.0
        start = end + 1
    return ranks


def _two_sided_p(observed: float, permuted: np.ndarray) -> float:
    if math.isnan(observed):
        return math.nan
    at_least_as_extreme = np.count_nonzero(np.abs(permuted) >= abs(observed))
    return (at_least_as_extreme + 1) / (permuted.size + 1)


def _sign_test_p(negative: int, positive: int) -> float:
    trials = negative + positive
    if trials == 0:
        return math.nan
    tail = sum(math.comb(trials, count) for count in range(min(negative, positive) + 1))
    return min(1.0, 2.0 * tail / 2 ** trials)
