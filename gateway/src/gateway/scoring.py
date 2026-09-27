"""Accuracy, calibration and latency statistics for benchmark runs.

Calibration uses `p_top`, the probability an engine put on the answer it chose.
- ECE: 10 equal-width bins of p_top; weighted mean |accuracy − mean p_top|.
- Brier: mean squared error of the full distribution against the one-hot gold answer.
- wrong@95: share of answered items that were wrong while p_top ≥ 0.95.
- auto@95: the largest share of all items you could accept automatically, most confident
  first, while keeping accuracy ≥ 95% (TypeSafe's "automate at a 5% error budget").
Unanswered items (errors) count as wrong for accuracy, and are left out of calibration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

BINS = 10


@dataclass
class Scored:
    correct: bool
    p_top: float
    brier: float
    predicted: str
    gold: str
    abs_error: float | None = None


def score_item(question: dict[str, Any], gold: Any, answer: dict[str, Any]) -> Scored:
    kind = question["type"]
    if kind == "choice":
        labels = list(answer["probabilities"])
        brier = sum((p - (1.0 if label == gold else 0.0)) ** 2 for label, p in answer["probabilities"].items())
        if gold not in labels:
            raise ValueError(f"gold label {gold!r} is not an option")
        return Scored(answer["choice"] == gold, answer["p_top"], brier, answer["choice"], str(gold))
    if kind == "score":
        g = int(gold)
        probs = [answer["probabilities"][str(i)] for i in range(len(answer["probabilities"]))]
        if not 0 <= g < len(probs):
            raise ValueError(f"gold level {g} is out of range")
        brier = sum((p - (1.0 if i == g else 0.0)) ** 2 for i, p in enumerate(probs))
        return Scored(answer["level"] == g, answer["p_top"], brier, str(answer["level"]), str(g),
                      abs_error=abs(answer["score"] - g))
    p = answer["noul"]
    g = bool(gold)
    brier = (p - float(g)) ** 2 + ((1 - p) - float(not g)) ** 2
    predicted = p >= 0.5
    return Scored(predicted == g, answer["p_top"], brier, str(predicted).lower(), str(g).lower())


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * q / 100
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def latency_stats(values: list[float]) -> dict[str, float | None]:
    return {"n": len(values), "mean": sum(values) / len(values) if values else None,
            "p50": percentile(values, 50), "p95": percentile(values, 95), "p99": percentile(values, 99),
            "min": min(values) if values else None, "max": max(values) if values else None}


def reliability(scored: list[Scored]) -> list[dict[str, Any]]:
    bins = []
    for b in range(BINS):
        lo, hi = b / BINS, (b + 1) / BINS
        members = [s for s in scored if lo <= s.p_top < hi or (b == BINS - 1 and s.p_top == 1.0)]
        bins.append({"lo": lo, "hi": hi, "n": len(members),
                     "confidence": sum(s.p_top for s in members) / len(members) if members else None,
                     "accuracy": sum(s.correct for s in members) / len(members) if members else None})
    return bins


def ece(scored: list[Scored]) -> float | None:
    if not scored:
        return None
    n = len(scored)
    return sum(b["n"] / n * abs(b["accuracy"] - b["confidence"]) for b in reliability(scored) if b["n"])


def auto_accept_at(scored: list[Scored], total: int, precision: float = 0.95) -> float:
    ranked = sorted(scored, key=lambda s: -s.p_top)
    best, right = 0, 0
    for k, s in enumerate(ranked, start=1):
        right += s.correct
        if right / k >= precision:
            best = k
    return best / total if total else 0.0


def confusion(scored: list[Scored], labels: list[str]) -> dict[str, Any]:
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for s in scored:
        if s.gold in index and s.predicted in index:
            matrix[index[s.gold]][index[s.predicted]] += 1
    return {"labels": labels, "matrix": matrix}


def summarise(scored: list[Scored], total: int, labels: list[str] | None = None) -> dict[str, Any]:
    answered = len(scored)
    correct = sum(s.correct for s in scored)
    out: dict[str, Any] = {
        "items": total, "answered": answered,
        "coverage": answered / total if total else 0.0,
        "accuracy": correct / total if total else 0.0,
        "accuracy_answered": correct / answered if answered else None,
        "ece": ece(scored),
        "brier": sum(s.brier for s in scored) / answered if answered else None,
        "wrong_at_95": sum(1 for s in scored if s.p_top >= 0.95 and not s.correct) / answered if answered else None,
        "auto_at_95": auto_accept_at(scored, total),
        "mean_p_top": sum(s.p_top for s in scored) / answered if answered else None,
        "reliability": reliability(scored),
    }
    errors = [s.abs_error for s in scored if s.abs_error is not None]
    if errors:
        out["mae"] = sum(errors) / len(errors)
    if labels:
        out["confusion"] = confusion(scored, labels)
    return out
