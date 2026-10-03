"""Fast, hermetic tests for the request observer.

A stub router stands in for laya.Router, so nothing is downloaded and no
checkpoint is loaded. The real-checkpoint end-to-end test lives in
test_server.py.
"""
import json
import logging
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient
from laya.serve import MAX_BODY_BYTES

from tryout_laya.recorder import canonical_input_hash
from tryout_laya.server import build_observed_app

STATE = "Put the oats in a blender, add the protein powder and berries."
QUESTIONS = {"isRecipe": {"type": "noul", "instructions": "Is this a recipe?"}}

RESULT = {
    "model": "laya-rl-agent",
    "answers": {
        "isStory": {"type": "noul", "noul": 0.12},
        "isRecipe": {"type": "noul", "noul": 0.93},
    },
    "usage": {"input_tokens": 164, "output_tokens": 0},
    "routing": {"model": "english", "reason": "English Latin text",
                "detection": None, "workflow": None},
}


class StubRouter:
    loaded = ["english"]

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def predict(self, state, questions, model=None):
        self.calls.append({"state": state, "questions": questions, "model": model})
        if self.error is not None:
            raise self.error
        return json.loads(json.dumps(RESULT))


@pytest.fixture
def build(tmp_path, monkeypatch):
    db_path = tmp_path / "requests.db"

    def _build(*, storage=True, debug=False, max_chars=None, error=None):
        monkeypatch.delenv("LAYA_REQUESTS_DB", raising=False)
        if storage:
            monkeypatch.setenv("LAYA_REQUESTS_DB", str(db_path))
        monkeypatch.setenv("LAYA_DEBUG_REQUESTS", "1" if debug else "0")
        if max_chars is None:
            monkeypatch.delenv("LAYA_DEBUG_MAX_CHARS", raising=False)
        else:
            monkeypatch.setenv("LAYA_DEBUG_MAX_CHARS", str(max_chars))
        router = StubRouter(error=error)
        return build_observed_app(router=router), router, db_path

    return _build


def request_body(**extra):
    return {"state": STATE, "questions": QUESTIONS, **extra}


def read_rows(db_path):
    if not db_path.exists():
        return []
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute("SELECT * FROM requests ORDER BY id")]
    finally:
        connection.close()


def request_log_records(caplog):
    return [record for record in caplog.records if record.name == "tryout_laya.requests"]


def test_metadata_absent_changes_nothing(build):
    app, router, db_path = build()
    with TestClient(app) as client:
        response = client.post("/v1/systemone", json=request_body())
    assert response.status_code == 200
    assert response.json() == RESULT
    assert read_rows(db_path) == []


def test_valid_metadata_is_stored(build):
    app, router, db_path = build()
    metadata = {"clientId": "videosvc", "timestamp": 12.5}
    body = request_body(metadata=metadata)
    with TestClient(app) as client:
        response = client.post("/v1/systemone", json=body)
    assert response.status_code == 200

    rows = read_rows(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["client_id"] == "videosvc"
    assert row["model"] == "english"
    assert row["content_hash"] == canonical_input_hash(STATE, QUESTIONS)
    assert json.loads(row["metadata"]) == metadata
    assert json.loads(row["request"]) == body
    assert json.loads(row["response"]) == RESULT
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", row["recorded_at"])


def test_metadata_without_client_id_is_rejected(build):
    app, router, db_path = build()
    with TestClient(app) as client:
        response = client.post("/v1/systemone",
                               json=request_body(metadata={"timestamp": 12.5}))
    assert response.status_code == 400
    assert response.json() == {"detail": "'metadata.clientId' must be a non-empty string"}
    assert router.calls == []
    assert read_rows(db_path) == []


@pytest.mark.parametrize("client_id", ["", "   ", 42, None, True, ["videosvc"]])
def test_invalid_client_id_is_rejected(build, client_id):
    app, router, db_path = build()
    with TestClient(app) as client:
        response = client.post("/v1/systemone",
                               json=request_body(metadata={"clientId": client_id}))
    assert response.status_code == 400
    assert response.json() == {"detail": "'metadata.clientId' must be a non-empty string"}
    assert router.calls == []
    assert read_rows(db_path) == []


@pytest.mark.parametrize("metadata", ["videosvc", [1, 2], 3, True, None])
def test_non_object_metadata_is_rejected(build, metadata):
    app, router, db_path = build()
    with TestClient(app) as client:
        response = client.post("/v1/systemone", json=request_body(metadata=metadata))
    assert response.status_code == 400
    assert response.json() == {"detail": "'metadata' must be a JSON object"}
    assert router.calls == []
    assert read_rows(db_path) == []


def test_storage_off_creates_no_db(build):
    app, router, db_path = build(storage=False)
    with TestClient(app) as client:
        response = client.post("/v1/systemone",
                               json=request_body(metadata={"clientId": "videosvc"}))
    assert response.status_code == 200
    assert not db_path.exists()


def test_metadata_contract_holds_with_storage_off(build):
    app, router, db_path = build(storage=False)
    with TestClient(app) as client:
        response = client.post("/v1/systemone", json=request_body(metadata="videosvc"))
    assert response.status_code == 400
    assert response.json() == {"detail": "'metadata' must be a JSON object"}
    assert not db_path.exists()


@pytest.mark.parametrize("error, expected", [(RuntimeError("boom"), 500), (ValueError("bad question"), 422)])
def test_failed_inference_is_not_stored(build, error, expected):
    app, router, db_path = build(error=error)
    with TestClient(app) as client:
        response = client.post("/v1/systemone",
                               json=request_body(metadata={"clientId": "videosvc"}))
    assert response.status_code == expected
    assert read_rows(db_path) == []


def test_content_hash_groups_repeated_inputs(build):
    app, router, db_path = build()
    with TestClient(app) as client:
        for _ in range(2):
            client.post("/v1/systemone",
                        json=request_body(metadata={"clientId": "videosvc"}))
        client.post("/v1/systemone",
                    json={"state": STATE + "!", "questions": QUESTIONS,
                          "metadata": {"clientId": "videosvc"}})

    rows = read_rows(db_path)
    assert len(rows) == 3
    assert rows[0]["content_hash"] == rows[1]["content_hash"]
    assert rows[0]["content_hash"] != rows[2]["content_hash"]

    connection = sqlite3.connect(db_path)
    try:
        groups = connection.execute(
            "SELECT client_id, content_hash, COUNT(*) AS repeats FROM requests "
            "GROUP BY client_id, content_hash HAVING repeats > 1").fetchall()
    finally:
        connection.close()
    assert len(groups) == 1
    assert groups[0][0] == "videosvc"
    assert groups[0][2] == 2


def test_debug_on_logs_the_exchange(build, caplog):
    app, router, db_path = build(debug=True)
    with caplog.at_level(logging.INFO, logger="tryout_laya.requests"):
        with TestClient(app) as client:
            client.post("/v1/systemone",
                        json=request_body(metadata={"clientId": "videosvc"}))
    records = request_log_records(caplog)
    assert len(records) == 1
    block = records[0].getMessage()
    assert "POST /v1/systemone -> 200" in block
    assert "clientId=videosvc" in block
    assert "model=english" in block
    assert STATE in block
    assert "isRecipe=0.93" in block


def test_debug_off_logs_nothing(build, caplog):
    app, router, db_path = build(debug=False)
    with caplog.at_level(logging.INFO, logger="tryout_laya.requests"):
        with TestClient(app) as client:
            client.post("/v1/systemone",
                        json=request_body(metadata={"clientId": "videosvc"}))
    assert request_log_records(caplog) == []


def test_error_is_logged(build, caplog):
    app, router, db_path = build(debug=True)
    with caplog.at_level(logging.INFO, logger="tryout_laya.requests"):
        with TestClient(app) as client:
            client.post("/v1/systemone", json=request_body(metadata={"timestamp": 1}))
    records = request_log_records(caplog)
    assert len(records) == 1
    block = records[0].getMessage()
    assert "-> 400" in block
    assert "status=400" in block
    assert "non-empty string" in block


def test_long_fields_are_truncated(build, caplog):
    app, router, db_path = build(debug=True, max_chars=10)
    with caplog.at_level(logging.INFO, logger="tryout_laya.requests"):
        with TestClient(app) as client:
            client.post("/v1/systemone",
                        json=request_body(metadata={"clientId": "videosvc"}))
    block = request_log_records(caplog)[0].getMessage()
    assert "…(+" in block


def test_health_is_never_observed(build, caplog):
    app, router, db_path = build(debug=True)
    with caplog.at_level(logging.INFO, logger="tryout_laya.requests"):
        with TestClient(app) as client:
            response = client.get("/health")
    assert response.status_code == 200
    assert request_log_records(caplog) == []
    assert read_rows(db_path) == []


def test_oversized_body_is_rejected_locally(build):
    app, router, db_path = build()
    with TestClient(app) as client:
        response = client.post("/v1/systemone",
                               content=b"x" * (MAX_BODY_BYTES + 1),
                               headers={"content-type": "application/json"})
    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}
    assert router.calls == []
    assert read_rows(db_path) == []
