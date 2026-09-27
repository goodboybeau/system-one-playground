import json

import httpx
import pytest

import engine_jev

ANSWERS = {"team": {"type": "choice", "choice": "billing", "confidence": 0.8,
                    "probabilities": {"billing": 0.9, "tech": 0.1}}}
Q = {"team": {"type": "choice", "instructions": "Which team?", "criteria": {"billing": None, "tech": None}}}


def fake(statuses=(200,), key="good"):
    calls = {"posts": [], "statuses": list(statuses)}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.headers["authorization"] != f"Bearer {key}":
            return httpx.Response(401, json={"detail": "invalid key"})
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [{"name": "jev-1.13.0"}, {"name": "jev-latest"}]})
        body = json.loads(req.content)
        calls["posts"].append(body)
        status = calls["statuses"].pop(0) if calls["statuses"] else 200
        if status == 200:
            return httpx.Response(200, json={"model": "jev-1.13.0", "answers": ANSWERS, "usage": {"input_tokens": 42, "output_tokens": 0}})
        if status == 422:
            return httpx.Response(422, json={"detail": "criteria must have at least 2 options"})
        return httpx.Response(status, json={"error": "busy"})

    return calls, httpx.Client(transport=httpx.MockTransport(handler))


def make(statuses=(200,), key="good"):
    calls, client = fake(statuses)
    return calls, engine_jev.JevPredictor("jev-1.13.0", key, "https://api.example", client)


def test_forwards_request_with_pinned_model(monkeypatch):
    calls, p = make()
    r = p.predict("charged twice", Q)
    assert r["answers"] == ANSWERS and r["usage"]["input_tokens"] == 42
    assert calls["posts"][0] == {"model": "jev-1.13.0", "state": "charged twice", "questions": Q}
    assert "jev-1.13.0" in p.info()["available_models"]


def test_retries_rate_limits(monkeypatch):
    monkeypatch.setattr(engine_jev.time, "sleep", lambda s: None)
    calls, p = make(statuses=(429, 529, 200))
    assert p.predict("x", Q)["answers"] == ANSWERS
    assert len(calls["posts"]) == 3


def test_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(engine_jev.time, "sleep", lambda s: None)
    _, p = make(statuses=(429,) * 10)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        p.predict("x", Q)


def test_validation_error_becomes_value_error():
    _, p = make(statuses=(422,))
    with pytest.raises(ValueError, match="at least 2 options"):
        p.predict("x", Q)


def test_bad_key_fails_at_load():
    _, client = fake()
    with pytest.raises(RuntimeError, match="rejected the API key"):
        engine_jev.JevPredictor("jev-1.13.0", "bad", "https://api.example", client)


def test_missing_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY is not set"):
        engine_jev.load("jev-1.13.0", "remote", None)
