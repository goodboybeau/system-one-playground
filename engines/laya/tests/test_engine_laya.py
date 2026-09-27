"""Needs the Laya weights (downloaded on first run). Runs on CPU so it works anywhere."""

import pytest

import engine_laya
from laya.common import build_sequence, serialize_state

Q = {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "refunds", "tech": "bugs"}}


@pytest.fixture(scope="module")
def predictor():
    return engine_laya.load("english", "cpu", 4)


def kept_state_tokens(p, state, q):
    tok = p.agent.tok
    internal = p.agent._to_internal(q)
    ids = tok(serialize_state(state), add_special_tokens=False)["input_ids"]
    full, _ = build_sequence(tok, state, internal, p.max_len, p.head_max_len, state_ids=ids)
    head, _ = build_sequence(tok, state, internal, p.max_len, p.head_max_len, state_ids=[])
    return len(ids), len(full) - len(head)


def test_short_state_has_no_warning(predictor):
    r = predictor.predict("I was charged twice", {"team": Q})
    assert r["warnings"] == []


def test_truncation_warning_matches_what_laya_keeps(predictor):
    state = "The invoice was charged twice. " * 200
    total, kept = kept_state_tokens(predictor, state, Q)
    assert kept < total
    r = predictor.predict(state, {"team": Q})
    assert r["warnings"] == [f"team: state truncated to {kept} of {total} tokens"]


def test_state_that_exactly_fits_is_not_flagged(predictor):
    tok = predictor.agent.tok
    words = []
    while True:
        words.append("refund")
        total, kept = kept_state_tokens(predictor, " ".join(words), Q)
        if total > kept:
            words.pop()
            break
    r = predictor.predict(" ".join(words), {"team": Q})
    assert r["warnings"] == []


def test_criteria_only_noul_gets_instructions(predictor):
    q = {"type": "noul", "criteria": {"true": "item arrived damaged", "false": "item is fine"}}
    r = predictor.predict("Order arrived smashed to pieces.", {"damaged": q})
    assert 0 <= r["answers"]["damaged"]["noul"] <= 1
    assert engine_laya._with_instructions(q)["instructions"] == "Is this true: item arrived damaged?"
    assert engine_laya._with_instructions({"type": "noul", "criteria": {"false": "fine"}})["instructions"] == "Is this true: not: fine?"


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="unknown Laya model"):
        engine_laya.load("klingon", "cpu", None)
