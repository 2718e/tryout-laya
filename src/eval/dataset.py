"""Read saved request/response pairs as per-line probability observations.

Only choice questions that offer exactly ``required_lines`` labelled lines plus a
``none`` option are usable. A label's position is rewritten as its offset from
the lowest label in the excerpt (``L071``..``L110`` becomes ``0``..``39``), so
excerpts taken from different points in a video can be pooled.
"""
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterator, Optional

REQUIRED_LINE_COUNT = 40
NONE_LABEL = "none"
_LINE_LABEL = re.compile(r"L(\d+)")


@dataclass(frozen=True)
class LineProbabilities:
    """One choice answer, with probabilities keyed by relative line position."""

    request_id: int
    recorded_at: str
    client_id: str
    question: str
    positions: tuple[int, ...]
    probabilities: tuple[float, ...]
    none_probability: float


@dataclass(frozen=True)
class RequestDataset:
    observations: tuple[LineProbabilities, ...]
    records_scanned: int
    records_excluded: int


def load_dataset(db_path, *, required_lines: int = REQUIRED_LINE_COUNT) -> RequestDataset:
    rows = _read_rows(db_path)
    observations = []
    excluded = 0
    for row in rows:
        found = _observations_from_row(row, required_lines)
        if found:
            observations.extend(found)
        else:
            excluded += 1
    return RequestDataset(tuple(observations), len(rows), excluded)


def _read_rows(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            "SELECT id, recorded_at, client_id, request, response FROM requests ORDER BY id"
        ).fetchall()
    finally:
        connection.close()


def _observations_from_row(row, required_lines):
    request = _json_object(row["request"])
    response = _json_object(row["response"])
    if request is None or response is None:
        return []
    answers = response.get("answers")
    if not isinstance(answers, dict):
        return []

    found = []
    for name, question in _choice_questions(request):
        series = _line_series(question, answers.get(name), required_lines)
        if series is None:
            continue
        positions, probabilities, none_probability = series
        found.append(LineProbabilities(
            request_id=row["id"],
            recorded_at=row["recorded_at"],
            client_id=row["client_id"],
            question=name,
            positions=positions,
            probabilities=probabilities,
            none_probability=none_probability,
        ))
    return found


def _choice_questions(request) -> Iterator[tuple[str, dict]]:
    questions = request.get("questions")
    if not isinstance(questions, dict):
        return
    for name, question in questions.items():
        if isinstance(question, dict) and question.get("type") == "choice":
            yield name, question


def _line_series(question, answer, required_lines) -> Optional[tuple]:
    criteria = question.get("criteria")
    if not isinstance(criteria, dict) or NONE_LABEL not in criteria:
        return None
    labels = sorted((label for label in criteria if _LINE_LABEL.fullmatch(label)),
                    key=_line_number)
    if len(labels) != required_lines or not isinstance(answer, dict):
        return None

    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict):
        return None
    lowest = _line_number(labels[0])
    positions, values = [], []
    for label in labels:
        value = _probability(probabilities.get(label))
        if value is None:
            return None
        positions.append(_line_number(label) - lowest)
        values.append(value)

    none_probability = _probability(probabilities.get(NONE_LABEL))
    if none_probability is None:
        return None
    return tuple(positions), tuple(values), none_probability


def _line_number(label: str) -> int:
    return int(label[1:])


def _probability(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _json_object(text):
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
