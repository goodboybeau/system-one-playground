"""Needs the Kev 0.8B adapter, its Qwen3.5 base, and Apple Silicon (MLX)."""

import platform

import pytest

import engine_kev

pytestmark = pytest.mark.skipif(platform.machine() != "arm64", reason="needs Apple Silicon")


@pytest.fixture(scope="module")
def predictor():
    return engine_kev.load("jaredpalmer/kev-0.8b", "mlx", None)


def test_info(predictor):
    i = predictor.info()
    assert i["backend"] == "mlx" and i["base_model"] == "Qwen/Qwen3.5-0.8B-Base"


def test_predict_shape(predictor):
    r = predictor.predict("I was charged twice", {
        "team": {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "refunds", "tech": "bugs"}},
        "urgency": {"type": "score", "instructions": "How urgent?", "criteria": ["low", "high"]},
    })
    assert set(r["answers"]) == {"team", "urgency"}
    assert r["answers"]["team"]["choice"] == "billing"
    assert r["usage"]["input_tokens"] > 0


def test_unknown_device():
    with pytest.raises(ValueError, match="Kev runs on"):
        engine_kev.load("jaredpalmer/kev-0.8b", "tpu", None)
