"""Console report for the relative-line-position analysis.

    uv run python -m src.eval

Reads the saved exchanges from ``--db``, prints the average probability per
relative line position and the statistics that relate the two, then writes the
graph to ``--output``.
"""
import argparse
from pathlib import Path

from .dataset import REQUIRED_LINE_COUNT, load_dataset
from .plot import plot_position_probabilities
from .statistics import (
    average_by_position,
    correlations,
    linear_fit,
    per_request_correlations,
)

DEFAULT_DB = ".logs/requests.db"
DEFAULT_OUTPUT = "src/eval/output/position_probability.png"

_VALUE_HEADER = "  %8s  %12s  %11s  %8s"
_VALUE_ROW = "  %8d  %12.6f  %11.6f  %8d"


def main(argv=None) -> int:
    args = _parse_args(argv)
    dataset = load_dataset(args.db, required_lines=args.lines)
    if not dataset.observations:
        print("No requests with %d labelled lines plus a 'none' option in %s"
              % (args.lines, args.db))
        return 1

    position_means = average_by_position(dataset.observations)
    _report_dataset(args, dataset)
    _report_raw_values(position_means)
    _report_statistics(position_means, dataset.observations)

    output_path = Path(args.output)
    plot_position_probabilities(position_means, output_path)
    print("\ngraph: %s" % output_path)
    return 0


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="request database (default: %(default)s)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="graph path (default: %(default)s)")
    parser.add_argument("--lines", type=int, default=REQUIRED_LINE_COUNT,
                        help="labelled lines required per request (default: %(default)s)")
    return parser.parse_args(argv)


def _report_dataset(args, dataset) -> None:
    print("database: %s" % args.db)
    print("records:  %d scanned, %d excluded (not %d labelled lines plus 'none')"
          % (dataset.records_scanned, dataset.records_excluded, args.lines))
    print("answers:  %d choice answers across %d line positions"
          % (len(dataset.observations), len(set(
              position for observation in dataset.observations
              for position in observation.positions))))


def _report_raw_values(position_means) -> None:
    print("\nMean probability assigned to each relative line position")
    print(_VALUE_HEADER % ("position", "mean", "std dev", "n"))
    for position, mean, deviation, count in zip(
            position_means.positions, position_means.means,
            position_means.standard_deviations, position_means.counts):
        print(_VALUE_ROW % (int(position), mean, deviation, int(count)))
    print("\n  'none' option: mean %.6f over %d answers"
          % (position_means.none_mean, position_means.observation_count))


def _report_statistics(position_means, observations) -> None:
    print("\nCorrelation between relative line position and mean probability")
    for correlation in correlations(position_means):
        print("  %-8s %+.4f   permutation p = %.4f"
              % (correlation.method, correlation.coefficient, correlation.p_value))

    slope, intercept, r_squared = linear_fit(position_means)
    print("  linear fit: mean = %+.6f * position %+.6f  (R2 = %.4f)"
          % (slope, intercept, r_squared))

    per_request = per_request_correlations(observations)
    print("\nPer-request Spearman coefficient (position vs probability)")
    print("  mean %+.4f   median %+.4f   negative %d / positive %d   sign-test p = %.4f"
          % (per_request.mean, per_request.median, per_request.negative,
             per_request.positive, per_request.p_value))
    print("  coefficients: %s" % " ".join("%+.2f" % value for value in per_request.coefficients))


if __name__ == "__main__":
    raise SystemExit(main())
