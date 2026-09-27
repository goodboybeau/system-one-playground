import math

import pytest
from pydantic import ValidationError

from labkit import ContractError, choice_confidence, normalise_answers, parse_request, score_confidence


def req(**questions):
    return parse_request({"state": "hello", "questions": questions})


CHOICE = {"type": "choice", "instructions": "which?", "criteria": {"a": "first", "b": None, "c": "third"}}
SCORE = {"type": "score", "instructions": "how much?", "criteria": ["low", "mid", "high"]}
NOUL = {"type": "noul", "instructions": "is it?"}


class TestParse:
    def test_valid_request_round_trips_to_wire_form(self):
        r = req(c=CHOICE, s=SCORE, n=NOUL)
        wire = r.wire_questions()
        assert wire["c"]["criteria"] == {"a": "first", "b": None, "c": "third"}
        assert wire["s"]["criteria"] == ["low", "mid", "high"]
        assert wire["n"] == {"type": "noul", "instructions": "is it?"}

    def test_list_criteria_become_a_map(self):
        r = req(c={"type": "choice", "instructions": "x", "criteria": ["yes please", "no thanks"]})
        assert r.wire_questions()["c"]["criteria"] == {"yes please": None, "no thanks": None}

    def test_state_may_be_object_or_array(self):
        assert parse_request({"state": {"a": 1}, "questions": {"n": NOUL}}).state == {"a": 1}
        assert parse_request({"state": [1, 2], "questions": {"n": NOUL}}).state == [1, 2]

    @pytest.mark.parametrize("body, needle", [
        ({"questions": {"n": NOUL}}, "state"),
        ({"state": "x", "questions": {}}, "at least one question"),
        ({"state": "x", "questions": {"c": {**CHOICE, "criteria": {"only": None}}}}, "2-255 options"),
        ({"state": "x", "questions": {"c": {**CHOICE, "criteria": ["a", "a"]}}}, "unique"),
        ({"state": "x", "questions": {"c": {**CHOICE, "criteria": {" ": None, "b": None}}}}, "non-empty"),
        ({"state": "x", "questions": {"s": {**SCORE, "criteria": ["one"]}}}, "2-10 levels"),
        ({"state": "x", "questions": {"s": {**SCORE, "criteria": ["a", None]}}}, "description"),
        ({"state": "x", "questions": {"n": {"type": "noul"}}}, "instructions or criteria"),
        ({"state": "x", "questions": {"n": {**NOUL, "typo": 1}}}, "Extra inputs"),
        ({"state": "x", "questions": {"n": {"type": "maybe"}}}, "does not match any of the expected tags"),
        ({"state": "x" * 200_001, "questions": {"n": NOUL}}, "state too large"),
        ({"state": "x", "questions": {f"q{i}": NOUL for i in range(65)}}, "at most 64"),
    ])
    def test_rejects_bad_requests(self, body, needle):
        with pytest.raises(ValidationError) as e:
            parse_request(body)
        assert needle in str(e.value)

    def test_model_field_is_accepted(self):
        assert parse_request({"state": "x", "questions": {"n": NOUL}, "model": "jev-latest"}).model == "jev-latest"


class TestConfidence:
    def test_choice_uniform_is_zero_and_certain_is_one(self):
        assert choice_confidence([0.25] * 4) == pytest.approx(0)
        assert choice_confidence([1, 0, 0]) == pytest.approx(1)

    def test_choice_matches_typesafe_formula(self):
        assert choice_confidence([0.44, 0.56, 0.0]) == pytest.approx((3 * 0.56 - 1) / 2)

    def test_score_certain_is_one(self):
        assert score_confidence([0, 1, 0]) == pytest.approx(1)

    def test_score_matches_typesafe_formula(self):
        p = [0.34, 0.55, 0.10]
        spread = (1 + 0 + 1) / 3
        expected = 1 - (0.34 * 1 + 0.10 * 1) / spread
        assert score_confidence(p) == pytest.approx(expected)

    def test_score_confidence_is_clipped_at_zero(self):
        assert score_confidence([0.5, 0, 0.5]) == 0.0


class TestNormalise:
    def test_choice_is_renormalised_and_reranked(self):
        r = req(c=CHOICE)
        out = normalise_answers(r, {"c": {"choice": "a", "confidence": 0.9,
                                          "probabilities": {"a": 0.2, "b": 0.7, "c": 0.1}}})
        a = out["c"]
        assert a["choice"] == "b"
        assert list(a["probabilities"]) == ["a", "b", "c"]
        assert a["p_top"] == pytest.approx(0.7)
        assert a["confidence"] == pytest.approx((3 * 0.7 - 1) / 2)
        assert a["engine"] == {"choice": "a", "confidence": 0.9}

    def test_choice_label_mismatch_is_a_contract_error(self):
        with pytest.raises(ContractError, match="do not match"):
            normalise_answers(req(c=CHOICE), {"c": {"probabilities": {"a": 0.5, "b": 0.5}}})

    def test_probabilities_must_sum_to_one(self):
        with pytest.raises(ContractError, match="sum to"):
            normalise_answers(req(c=CHOICE), {"c": {"probabilities": {"a": 0.5, "b": 0.5, "c": 0.5}}})

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -0.2, 1.3, "0.5", True, None])
    def test_bad_probability_values(self, bad):
        with pytest.raises(ContractError):
            normalise_answers(req(n=NOUL), {"n": {"noul": bad}})

    def test_score_accepts_index_keys(self):
        out = normalise_answers(req(s=SCORE), {"s": {"probabilities": {"0": 0.1, "1": 0.2, "2": 0.7}}})
        a = out["s"]
        assert a["level"] == 2
        assert a["score"] == pytest.approx(0.2 + 1.4)
        assert a["legend"] == {"0": "low", "1": "mid", "2": "high"}

    def test_score_accepts_integer_and_description_keys(self):
        by_int = normalise_answers(req(s=SCORE), {"s": {"probabilities": {0: 0.6, 1: 0.3, 2: 0.1}}})
        by_text = normalise_answers(req(s=SCORE), {"s": {"probabilities": {"low": 0.6, "mid": 0.3, "high": 0.1}}})
        assert by_int["s"]["probabilities"] == by_text["s"]["probabilities"]

    def test_score_missing_level_is_a_contract_error(self):
        with pytest.raises(ContractError, match="cover 2 of 3"):
            normalise_answers(req(s=SCORE), {"s": {"probabilities": {"0": 0.5, "1": 0.5}}})

    def test_score_unknown_key_is_a_contract_error(self):
        with pytest.raises(ContractError, match="neither"):
            normalise_answers(req(s=SCORE), {"s": {"probabilities": {"0": 0.5, "1": 0.5, "9": 0}}})

    def test_noul(self):
        a = normalise_answers(req(n=NOUL), {"n": {"noul": 0.2}})["n"]
        assert a == {"type": "noul", "noul": 0.2, "confidence": pytest.approx(0.6), "p_top": pytest.approx(0.8),
                     "engine": {}}

    def test_missing_answer(self):
        with pytest.raises(ContractError, match="missing"):
            normalise_answers(req(n=NOUL, c=CHOICE), {"n": {"noul": 0.5}})

    def test_answers_must_be_objects(self):
        with pytest.raises(ContractError):
            normalise_answers(req(n=NOUL), None)
        with pytest.raises(ContractError):
            normalise_answers(req(n=NOUL), {"n": 0.5})
