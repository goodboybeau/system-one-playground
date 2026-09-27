"""The /v1/systemone wire contract every engine in the lab speaks.

Requests are parsed once into typed models. Engine answers are normalised into one
canonical shape so engines can be compared field for field:

    choice  {type, choice, probabilities{label: p}, confidence, p_top}
    score   {type, score, level, probabilities{"0": p, ...}, legend{"0": text}, confidence, p_top}
    noul    {type, noul, confidence, p_top}

`confidence` is recomputed from the probabilities with TypeSafe's published definition
(choice: (n·p_max − 1)/(n − 1); score: 1 − expected distance from the modal level over the
scale's mean distance from its middle). Engines disagree on how they define confidence, so the
engine's own value is kept under `engine` and never compared across engines. For noul, which
TypeSafe gives no confidence, the lab uses |2p − 1|. `p_top` is the probability on the chosen
answer and is what calibration metrics use.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_QUESTIONS = 64
MAX_CHOICE_OPTIONS = 255
MIN_SCORE_LEVELS = 2
MAX_SCORE_LEVELS = 10
MAX_STATE_CHARS = 200_000


class ContractError(ValueError):
    """An engine returned something that does not satisfy the contract."""


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instructions: Any = None


class ChoiceQuestion(_Question):
    type: Literal["choice"]
    criteria: dict[str, Any]

    @field_validator("criteria", mode="before")
    @classmethod
    def _list_to_map(cls, v: Any) -> Any:
        if isinstance(v, list):
            if not all(isinstance(x, str) for x in v):
                raise ValueError("list criteria must be option labels (strings)")
            if len(set(v)) != len(v):
                raise ValueError("option labels must be unique")
            return {label: None for label in v}
        return v

    @field_validator("criteria")
    @classmethod
    def _check_options(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not MIN_SCORE_LEVELS <= len(v) <= MAX_CHOICE_OPTIONS:
            raise ValueError(f"choice needs 2-{MAX_CHOICE_OPTIONS} options, got {len(v)}")
        if any(not k.strip() for k in v):
            raise ValueError("option labels must be non-empty")
        return v

    @property
    def labels(self) -> list[str]:
        return list(self.criteria)


class ScoreQuestion(_Question):
    type: Literal["score"]
    criteria: list[Any]

    @field_validator("criteria")
    @classmethod
    def _check_levels(cls, v: list[Any]) -> list[Any]:
        if not MIN_SCORE_LEVELS <= len(v) <= MAX_SCORE_LEVELS:
            raise ValueError(f"score needs {MIN_SCORE_LEVELS}-{MAX_SCORE_LEVELS} levels, got {len(v)}")
        if any(level is None or (isinstance(level, str) and not level.strip()) for level in v):
            raise ValueError("every score level needs a description")
        return v


class NoulQuestion(_Question):
    type: Literal["noul"]
    criteria: dict[Literal["true", "false"], Any] | None = None

    @model_validator(mode="after")
    def _needs_something(self) -> "NoulQuestion":
        if self.instructions in (None, "") and not self.criteria:
            raise ValueError("noul needs instructions or criteria")
        return self


Question = Annotated[Union[ChoiceQuestion, ScoreQuestion, NoulQuestion], Field(discriminator="type")]


class SystemOneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str | dict[str, Any] | list[Any]
    questions: dict[str, Question]
    model: str | None = None

    @field_validator("questions")
    @classmethod
    def _check_questions(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("at least one question is required")
        if len(v) > MAX_QUESTIONS:
            raise ValueError(f"at most {MAX_QUESTIONS} questions, got {len(v)}")
        if any(not k.strip() for k in v):
            raise ValueError("question ids must be non-empty")
        return v

    @field_validator("state")
    @classmethod
    def _check_state(cls, v: Any) -> Any:
        size = len(v) if isinstance(v, str) else len(repr(v))
        if size > MAX_STATE_CHARS:
            raise ValueError(f"state too large ({size} > {MAX_STATE_CHARS} chars)")
        return v

    def wire_questions(self) -> dict[str, dict[str, Any]]:
        """Questions as plain dicts in wire form, choice criteria always a map."""
        return {qid: q.model_dump(exclude_none=True) for qid, q in self.questions.items()}


def parse_request(body: Any) -> SystemOneRequest:
    return SystemOneRequest.model_validate(body)


def choice_confidence(probs: list[float]) -> float:
    n = len(probs)
    return _clip01((n * max(probs) - 1) / (n - 1))


def score_confidence(probs: list[float]) -> float:
    n = len(probs)
    k = max(range(n), key=probs.__getitem__)
    mid = (n - 1) / 2
    spread = sum(abs(i - mid) for i in range(n)) / n
    expected_distance = sum(p * abs(i - k) for i, p in enumerate(probs))
    return _clip01(1 - expected_distance / spread)


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _prob(qid: str, x: Any) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ContractError(f"{qid}: probability {x!r} is not a finite number")
    if x < -1e-6 or x > 1 + 1e-6:
        raise ContractError(f"{qid}: probability {x!r} outside [0, 1]")
    return _clip01(float(x))


def _normalised(qid: str, probs: list[float]) -> list[float]:
    total = sum(probs)
    if not 0.98 <= total <= 1.02:
        raise ContractError(f"{qid}: probabilities sum to {total:.4f}, expected 1")
    return [p / total for p in probs]


def _engine_extras(raw: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: raw[k] for k in keys if k in raw}


def _normalise_choice(qid: str, q: ChoiceQuestion, raw: dict[str, Any]) -> dict[str, Any]:
    probs_raw = raw.get("probabilities")
    if not isinstance(probs_raw, dict):
        raise ContractError(f"{qid}: choice answer has no probabilities map")
    labels = q.labels
    if set(probs_raw) != set(labels):
        raise ContractError(f"{qid}: probability labels {sorted(probs_raw)} do not match options {sorted(labels)}")
    probs = _normalised(qid, [_prob(qid, probs_raw[label]) for label in labels])
    top = max(range(len(labels)), key=probs.__getitem__)
    return {
        "type": "choice",
        "choice": labels[top],
        "probabilities": dict(zip(labels, probs)),
        "confidence": choice_confidence(probs),
        "p_top": probs[top],
        "engine": _engine_extras(raw, ("choice", "confidence")),
    }


def _score_index(qid: str, key: Any, legend: list[str]) -> int:
    s = str(key)
    if s.lstrip("-").isdigit() and 0 <= int(s) < len(legend):
        return int(s)
    if s in legend:
        return legend.index(s)
    raise ContractError(f"{qid}: score probability key {key!r} is neither a level index nor a level description")


def _normalise_score(qid: str, q: ScoreQuestion, raw: dict[str, Any]) -> dict[str, Any]:
    probs_raw = raw.get("probabilities")
    legend = [lvl if isinstance(lvl, str) else repr(lvl) for lvl in q.criteria]
    if not isinstance(probs_raw, dict):
        raise ContractError(f"{qid}: score answer has no probabilities map")
    probs = [0.0] * len(legend)
    seen: set[int] = set()
    for key, value in probs_raw.items():
        i = _score_index(qid, key, legend)
        if i in seen:
            raise ContractError(f"{qid}: level {i} appears twice in probabilities")
        seen.add(i)
        probs[i] = _prob(qid, value)
    if len(seen) != len(legend):
        raise ContractError(f"{qid}: probabilities cover {len(seen)} of {len(legend)} levels")
    probs = _normalised(qid, probs)
    level = max(range(len(probs)), key=probs.__getitem__)
    return {
        "type": "score",
        "score": sum(i * p for i, p in enumerate(probs)),
        "level": level,
        "probabilities": {str(i): p for i, p in enumerate(probs)},
        "legend": {str(i): text for i, text in enumerate(legend)},
        "confidence": score_confidence(probs),
        "p_top": probs[level],
        "engine": _engine_extras(raw, ("score", "confidence")),
    }


def _normalise_noul(qid: str, raw: dict[str, Any]) -> dict[str, Any]:
    if "noul" not in raw:
        raise ContractError(f"{qid}: noul answer has no 'noul' value")
    p = _prob(qid, raw["noul"])
    return {
        "type": "noul",
        "noul": p,
        "confidence": abs(2 * p - 1),
        "p_top": max(p, 1 - p),
        "engine": _engine_extras(raw, ("confidence",)),
    }


def normalise_answers(request: SystemOneRequest, raw_answers: Any) -> dict[str, dict[str, Any]]:
    """Check an engine's answers against the request and return them in canonical form."""
    if not isinstance(raw_answers, dict):
        raise ContractError("answers must be an object")
    missing = set(request.questions) - set(raw_answers)
    if missing:
        raise ContractError(f"answers missing for questions: {sorted(missing)}")
    out: dict[str, dict[str, Any]] = {}
    for qid, q in request.questions.items():
        raw = raw_answers[qid]
        if not isinstance(raw, dict):
            raise ContractError(f"{qid}: answer must be an object")
        if isinstance(q, ChoiceQuestion):
            out[qid] = _normalise_choice(qid, q, raw)
        elif isinstance(q, ScoreQuestion):
            out[qid] = _normalise_score(qid, q, raw)
        else:
            out[qid] = _normalise_noul(qid, raw)
    return out
