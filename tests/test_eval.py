"""Tests for the eval loader and statistics, on synthetic exchanges."""
import json

import pytest

from src.eval.dataset import load_dataset
from src.eval.statistics import average_by_position, correlations, per_request_correlations
from src.recorder import RequestRecord, SqliteRequestRecorder

LINES = ["L%03d" % number for number in range(71, 111)]


def write_exchange(db_path, *, request, response):
    recorder = SqliteRequestRecorder(str(db_path))
    recorder.record(RequestRecord(
        recorded_at="2026-10-04T00:00:00.000Z",
        client_id="synthetic",
        model="english",
        content_hash="0" * 64,
        metadata="{}",
        request=json.dumps(request),
        response=json.dumps(response),
    ))
    recorder.close()


def choice_request(labels=LINES, include_none=True):
    criteria = {label: None for label in labels}
    if include_none:
        criteria["none"] = "No line names the sponsor."
    return {"questions": {"anchor_line": {"type": "choice", "criteria": criteria}}}


def choice_response(labels=LINES, probabilities=None):
    values = dict(probabilities) if probabilities is not None else {
        label: 1.0 / len(labels) for label in labels}
    values.setdefault("none", 0.25)
    return {"answers": {"anchor_line": {"type": "choice", "probabilities": values}}}


def test_relative_positions_are_offsets_from_the_lowest_label(tmp_path):
    db_path = tmp_path / "requests.db"
    write_exchange(db_path, request=choice_request(), response=choice_response())

    dataset = load_dataset(db_path)
    assert dataset.records_scanned == 1
    assert dataset.records_excluded == 0

    observation, = dataset.observations
    assert observation.positions == tuple(range(40))
    assert observation.none_probability == 0.25
    assert len(observation.probabilities) == 40


@pytest.mark.parametrize("labels, include_none", [
    (LINES[:39], True),
    (LINES, False),
])
def test_wrong_shape_is_excluded(tmp_path, labels, include_none):
    db_path = tmp_path / "requests.db"
    write_exchange(db_path, request=choice_request(labels, include_none),
                   response=choice_response(labels))

    dataset = load_dataset(db_path)
    assert dataset.observations == ()
    assert dataset.records_excluded == 1


def test_answer_missing_a_probability_is_excluded(tmp_path):
    db_path = tmp_path / "requests.db"
    response = choice_response()
    del response["answers"]["anchor_line"]["probabilities"][LINES[5]]
    write_exchange(db_path, request=choice_request(), response=response)

    assert load_dataset(db_path).observations == ()


def test_non_choice_question_is_ignored(tmp_path):
    db_path = tmp_path / "requests.db"
    request = {"questions": {"sponsor_starts_here": {"type": "noul", "criteria": {"true": "x"}}}}
    write_exchange(db_path, request=request, response={"answers": {}})

    assert load_dataset(db_path).observations == ()


def test_probability_falls_with_position(tmp_path):
    db_path = tmp_path / "requests.db"
    declining = {label: float(40 - index) for index, label in enumerate(LINES)}
    for _ in range(3):
        write_exchange(db_path, request=choice_request(),
                       response=choice_response(probabilities=declining))

    dataset = load_dataset(db_path)
    position_means = average_by_position(dataset.observations)
    pearson, spearman = correlations(position_means, permutations=200)

    assert position_means.positions.tolist() == list(range(40))
    assert pearson.coefficient < 0
    assert spearman.coefficient < 0
    assert per_request_correlations(dataset.observations).negative == 3
