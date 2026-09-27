"""Needs decider-0.8b weights and an Apple GPU (MPS)."""

import pytest
import torch

import engine_decider

pytestmark = pytest.mark.skipif(not torch.backends.mps.is_available(), reason="needs MPS")


@pytest.fixture(scope="module")
def predictor():
    return engine_decider.load("Mapika/decider-0.8b", "mps", None)


def test_info(predictor):
    i = predictor.info()
    assert i["layout"] == "plain" and i["dtype"] == "float16" and i["params"] > 7e8


def test_predict_shape(predictor):
    r = predictor.predict("I was charged twice", {
        "team": {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "refunds", "tech": "bugs"}},
        "calm": {"type": "noul", "criteria": {"true": "customer is calm", "false": "customer is upset"}},
    })
    assert set(r["answers"]) == {"team", "calm"}
    assert r["answers"]["team"]["choice"] == "billing"
    assert r["usage"]["input_tokens"] > 0
