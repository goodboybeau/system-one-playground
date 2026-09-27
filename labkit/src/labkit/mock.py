"""A deterministic engine with no weights, for tests and for exercising the lab offline.

It scores options by word overlap between the state and each option's label and
description. Model names select behaviour:

    lexical        the default: word overlap, instant
    slow:<ms>      the same, sleeping <ms> per request
    broken         answers that violate the contract (probabilities that do not sum to 1)
    warn-load      loads, emitting a RuntimeWarning
    fail-load      raises while loading
    fail-predict   raises on every request
    exit-load      the process exits with code 3 while loading
    probe-network  tries to reach the internet while loading; /info reports whether it could
"""

from __future__ import annotations

import json
import math
import re
import time
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")


def _words(x: Any) -> set[str]:
    text = x if isinstance(x, str) else json.dumps(x, sort_keys=True, default=str)
    return set(_WORD.findall(text.lower()))


def _softmax(xs: list[float]) -> list[float]:
    m = max(xs)
    es = [math.exp(x - m) for x in xs]
    total = sum(es)
    return [e / total for e in es]


class MockPredictor:
    def __init__(self, model: str):
        self.model = model
        self.delay_s = 0.0
        if model.startswith("slow:"):
            self.delay_s = float(model.split(":", 1)[1]) / 1000

    network: str | None = None

    def info(self) -> dict[str, Any]:
        out: dict[str, Any] = {"backend": "mock", "params": 0, "dtype": "n/a"}
        if self.network is not None:
            out["network"] = self.network
        return out

    def _overlap(self, state_words: set[str], *texts: Any) -> float:
        words = set().union(*(_words(t) for t in texts if t is not None))
        return 2.0 * len(state_words & words) / (1 + len(words)) ** 0.5

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if self.model == "fail-predict":
            raise RuntimeError("mock engine configured to fail")
        if self.delay_s:
            time.sleep(self.delay_s)
        sw = _words(state)
        answers: dict[str, Any] = {}
        for qid, q in questions.items():
            if q["type"] == "choice":
                labels = list(q["criteria"])
                probs = _softmax([self._overlap(sw, label, q["criteria"][label]) for label in labels])
                if self.model == "broken":
                    probs = [p * 3 for p in probs]
                answers[qid] = {"choice": labels[probs.index(max(probs))], "probabilities": dict(zip(labels, probs))}
            elif q["type"] == "score":
                probs = _softmax([self._overlap(sw, level) for level in q["criteria"]])
                answers[qid] = {"score": sum(i * p for i, p in enumerate(probs)),
                                "probabilities": {str(i): p for i, p in enumerate(probs)}}
            else:
                s = self._overlap(sw, q.get("instructions"), (q.get("criteria") or {}).get("true"))
                answers[qid] = {"noul": 1 / (1 + math.exp(-(s - 1.0)))}
        return {"answers": answers, "usage": {"input_tokens": len(sw), "output_tokens": 0}}


def load(model: str, device: str, threads: int | None) -> MockPredictor:
    if model == "warn-load":
        import warnings

        warnings.warn("mock checkpoint ships uncalibrated temperatures", RuntimeWarning)
    if model == "fail-load":
        raise RuntimeError("mock engine configured to fail while loading")
    if model == "exit-load":
        import os

        os._exit(3)
    predictor = MockPredictor(model)
    if model == "probe-network":
        import socket

        try:
            socket.create_connection(("1.1.1.1", 443), timeout=3).close()
            predictor.network = "open"
        except OSError as e:
            predictor.network = f"blocked ({e.__class__.__name__})"
    return predictor
