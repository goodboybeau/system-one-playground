import pytest

from gateway.scoring import Scored, auto_accept_at, ece, latency_stats, percentile, reliability, score_item, summarise

CHOICE = {"type": "choice"}
SCORE = {"type": "score"}
NOUL = {"type": "noul"}


def choice_answer(probs):
    top = max(probs, key=probs.get)
    return {"choice": top, "probabilities": probs, "p_top": probs[top]}


def test_choice_scoring_and_brier():
    s = score_item(CHOICE, "a", choice_answer({"a": 0.7, "b": 0.2, "c": 0.1}))
    assert s.correct and s.p_top == 0.7
    assert s.brier == pytest.approx(0.3**2 + 0.2**2 + 0.1**2)


def test_choice_gold_must_be_an_option():
    with pytest.raises(ValueError, match="not an option"):
        score_item(CHOICE, "z", choice_answer({"a": 0.5, "b": 0.5}))


def test_score_scoring_uses_modal_level_and_expected_value_error():
    ans = {"level": 2, "score": 1.6, "p_top": 0.6, "probabilities": {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1}}
    s = score_item(SCORE, 1, ans)
    assert not s.correct and s.abs_error == pytest.approx(0.6)
    assert s.brier == pytest.approx(0.1**2 + 0.8**2 + 0.6**2 + 0.1**2)


def test_noul_threshold_and_brier():
    s = score_item(NOUL, True, {"noul": 0.8, "p_top": 0.8})
    assert s.correct and s.predicted == "true"
    assert s.brier == pytest.approx(0.2**2 * 2)
    assert not score_item(NOUL, False, {"noul": 0.5, "p_top": 0.5}).correct


def test_percentile_interpolates_like_numpy():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([10], 99) == 10
    assert percentile([], 50) is None
    assert percentile(list(range(101)), 95) == 95


def test_latency_stats():
    s = latency_stats([10.0, 20.0, 30.0])
    assert s["mean"] == 20 and s["p50"] == 20 and s["min"] == 10 and s["max"] == 30


def mk(p, ok):
    return Scored(ok, p, 0.0, "x", "x" if ok else "y")


def test_perfect_calibration_has_zero_ece():
    scored = [mk(0.75, True)] * 3 + [mk(0.75, False)]
    assert ece(scored) == pytest.approx(0)


def test_overconfidence_shows_in_ece():
    scored = [mk(0.95, True), mk(0.95, False)]
    assert ece(scored) == pytest.approx(0.45)


def test_reliability_puts_one_in_the_last_bin():
    bins = reliability([mk(1.0, True), mk(0.0, False)])
    assert bins[-1]["n"] == 1 and bins[0]["n"] == 1


def test_auto_accept_counts_the_confident_prefix():
    scored = [mk(0.99, True)] * 19 + [mk(0.98, False)] + [mk(0.6, False)] * 20
    assert auto_accept_at(scored, 40) == pytest.approx(20 / 40)
    assert auto_accept_at([mk(0.9, False)], 1) == 0


def test_summary_counts_unanswered_as_wrong():
    scored = [mk(0.96, True), mk(0.97, False)]
    s = summarise(scored, total=4, labels=["x", "y"])
    assert s["accuracy"] == 0.25 and s["accuracy_answered"] == 0.5 and s["coverage"] == 0.5
    assert s["wrong_at_95"] == 0.5
    assert s["confusion"]["matrix"] == [[1, 0], [1, 0]]


def test_summary_of_nothing():
    s = summarise([], total=0)
    assert s["accuracy"] == 0 and s["ece"] is None and s["brier"] is None
