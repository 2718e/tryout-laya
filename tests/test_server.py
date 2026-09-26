"""End-to-end test: the served HTTP surface must answer typed questions.

This loads a real checkpoint on first run (roughly 800 MB, cached under HF_HOME),
so it is slower than a unit test and needs network access the first time.
"""
import pytest
from fastapi.testclient import TestClient

import laya
from laya.serve import create_app

STATE = "Hi, we were billed twice for March. Please refund the duplicate today."
QUESTIONS = {
    "churn_risk": {
        "type": "noul",
        "instructions": "Does the user threaten to cancel or leave?",
    }
}


@pytest.fixture(scope="module")
def client():
    # An explicit Router keeps the test to one checkpoint however the server
    # environment is configured.
    router = laya.Router(device="cpu", preload=["english"])
    with TestClient(create_app(router)) as client:
        yield client


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_systemone_answers_typed_question(client):
    response = client.post("/v1/systemone", json={"state": STATE, "questions": QUESTIONS})
    assert response.status_code == 200, response.text

    answer = response.json()["answers"]["churn_risk"]
    assert 0.0 <= answer["noul"] <= 1.0


def test_malformed_question_is_rejected(client):
    bad = {"bad": {"type": "nonsense", "instructions": "?"}}
    response = client.post("/v1/systemone", json={"state": STATE, "questions": bad})
    assert response.status_code == 422
