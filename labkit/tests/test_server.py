import time

import pytest
from fastapi.testclient import TestClient

from labkit import mock
from labkit.server import EngineState, create_app

BODY = {
    "state": "I was charged twice, please refund my payment",
    "questions": {
        "team": {"type": "choice", "instructions": "team?",
                 "criteria": {"billing": "payment refund charged", "tech": "bugs crashes"}},
        "urgency": {"type": "score", "instructions": "urgency?", "criteria": ["calm", "refund now"]},
        "refund": {"type": "noul", "instructions": "asks for a refund?"},
    },
}


def client_for(model: str):
    state = EngineState("labkit.mock:load", model, "cpu", None)
    return state, TestClient(create_app(state, mock.load))


def wait_until_settled(c: TestClient, timeout: float = 5) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        h = c.get("/healthz").json()
        if h["status"] in ("ready", "error"):
            return h
        time.sleep(0.01)
    raise AssertionError("engine never settled")


def test_happy_path():
    state, raw = client_for("lexical")
    with raw as c:
        h = wait_until_settled(c)
        assert h["status"] == "ready" and h["load_seconds"] is not None and h["warmup_ms"] is not None
        r = c.post("/v1/systemone", json=BODY)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["answers"]["team"]["choice"] == "billing"
        assert body["answers"]["urgency"]["type"] == "score"
        assert 0 <= body["answers"]["refund"]["noul"] <= 1
        assert body["usage"]["output_tokens"] == 0
        assert float(r.headers["x-infer-ms"]) >= 0
        assert set(body["raw_answers"]) == {"team", "urgency", "refund"}
        info = c.get("/info").json()
        assert info["backend"] == "mock" and info["status"] == "ready" and info["pid"] > 0


@pytest.mark.parametrize("payload, status", [
    ("not json", 400),
    ({"state": "x"}, 422),
    ({"state": "x", "questions": {"n": {"type": "noul"}}}, 422),
])
def test_bad_requests(payload, status):
    _, raw = client_for("lexical")
    with raw as c:
        wait_until_settled(c)
        if isinstance(payload, str):
            r = c.post("/v1/systemone", content=payload, headers={"content-type": "application/json"})
        else:
            r = c.post("/v1/systemone", json=payload)
        assert r.status_code == status
        assert "error" in r.json()


def test_validation_errors_are_readable():
    _, raw = client_for("lexical")
    with raw as c:
        wait_until_settled(c)
        r = c.post("/v1/systemone", json={"state": "x", "questions": {"q": {"type": "score", "criteria": ["a"]}}})
        assert r.status_code == 422
        assert any("questions.q.criteria" in d and "2-10 levels" in d for d in r.json()["details"])


def test_load_failure_is_reported():
    _, raw = client_for("fail-load")
    with raw as c:
        h = wait_until_settled(c)
        assert h["status"] == "error" and "fail while loading" in h["error"]
        r = c.post("/v1/systemone", json=BODY)
        assert r.status_code == 503


def test_predict_failure_during_warmup_marks_engine_error():
    _, raw = client_for("fail-predict")
    with raw as c:
        h = wait_until_settled(c)
        assert h["status"] == "error" and "configured to fail" in h["error"]


def test_contract_violation_is_502():
    state, raw = client_for("lexical")
    with raw as c:
        wait_until_settled(c)
        state.predictor = mock.MockPredictor("broken")
        r = c.post("/v1/systemone", json=BODY)
        assert r.status_code == 502 and "contract" in r.json()["error"]


def test_predictor_value_error_is_422_and_other_errors_are_500():
    state, raw = client_for("lexical")
    with raw as c:
        wait_until_settled(c)

        class Raises:
            def __init__(self, exc):
                self.exc = exc

            def predict(self, *_):
                raise self.exc

            def info(self):
                return {}

        state.predictor = Raises(ValueError("too many options for this model"))
        r = c.post("/v1/systemone", json=BODY)
        assert r.status_code == 422 and "too many options" in r.json()["error"]
        state.predictor = Raises(RuntimeError("boom"))
        r = c.post("/v1/systemone", json=BODY)
        assert r.status_code == 500 and "RuntimeError: boom" in r.json()["error"]


def test_requests_are_serialised_on_one_worker():
    import concurrent.futures

    _, raw = client_for("slow:50")
    with raw as c:
        wait_until_settled(c)
        with concurrent.futures.ThreadPoolExecutor(4) as ex:
            rs = list(ex.map(lambda _: c.post("/v1/systemone", json=BODY), range(4)))
        assert all(r.status_code == 200 for r in rs)
        queues = sorted(r.json()["timing"]["queue_ms"] for r in rs)
        assert queues[-1] >= 100


def test_load_warnings_are_captured():
    _, raw = client_for("warn-load")
    with raw as c:
        assert wait_until_settled(c)["status"] == "ready"
        assert c.get("/info").json()["load_warnings"] == ["RuntimeWarning: mock checkpoint ships uncalibrated temperatures"]
