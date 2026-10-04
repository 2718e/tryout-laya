"""Graph of average probability against relative line position."""
import os
from pathlib import Path

# The container's $HOME is read-only, so matplotlib's default config directory
# is unusable; keep its cache with the project's other caches instead.
_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "matplotlib"
os.environ.setdefault("MPLCONFIGDIR", str(_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be chosen first)
import numpy as np  # noqa: E402

from .statistics import PositionMeans, linear_fit  # noqa: E402


def plot_position_probabilities(position_means: PositionMeans, output_path) -> None:
    positions = position_means.positions
    means = position_means.means
    errors = np.divide(position_means.standard_deviations, np.sqrt(position_means.counts),
                       out=np.zeros_like(means), where=position_means.counts > 0)
    slope, intercept, r_squared = linear_fit(position_means)

    figure, (linear, logarithmic) = plt.subplots(1, 2, figsize=(14, 5))

    _bars(linear, positions, means, errors)
    linear.plot(positions, slope * positions + intercept, color="crimson", linewidth=1.5,
                label="linear fit: %.4f·position + %.4f (R² = %.3f)"
                      % (slope, intercept, r_squared))
    linear.legend()
    linear.set_title("Average assigned probability by relative line position")
    linear.set_ylabel("Mean probability")

    _bars(logarithmic, positions, means, errors)
    logarithmic.set_yscale("log")
    logarithmic.set_title("Same values on a log scale")
    logarithmic.set_ylabel("Mean probability (log)")

    for axes in (linear, logarithmic):
        axes.set_xlabel("Relative line position")
        axes.grid(True, axis="y", alpha=0.3)

    figure.suptitle("Mean probability per relative line position over %d requests "
                    "(error bars: standard error of the mean)"
                    % position_means.observation_count)
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _bars(axes, positions, means, errors) -> None:
    axes.bar(positions, means, yerr=errors, capsize=2, color="steelblue",
             edgecolor="white", linewidth=0.4)
