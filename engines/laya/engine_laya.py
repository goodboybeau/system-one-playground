"""Laya (Convai Innovations): ModernBERT / mmBERT encoder with a decision head.

Models: english (repo root), multilingual, typed-decisions — subfolders of convaiinnovations/laya.
Laya truncates long state silently; this adapter measures the room each question leaves for
the state and reports a warning when the state did not fit.
"""

from __future__ import annotations

from typing import Any

import torch

import laya
from laya.common import build_sequence, serialize_state

REPO = "convaiinnovations/laya"
SUBFOLDERS = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}


class LayaPredictor:
    def __init__(self, model: str, device: str):
        if model not in SUBFOLDERS:
            raise ValueError(f"unknown Laya model {model!r}; expected one of {sorted(SUBFOLDERS)}")
        self.model = model
        self.agent = laya.load(REPO, device=device, subfolder=SUBFOLDERS[model])
        self.max_len = int(self.agent.cfg.get("max_len", 512))
        self.head_max_len = int(self.agent.cfg.get("head_max_len", 192))

    def info(self) -> dict[str, Any]:
        return {
            "backend": f"torch {torch.__version__}",
            "repo": REPO + (f"/{SUBFOLDERS[self.model]}" if SUBFOLDERS[self.model] else ""),
            "params": sum(p.numel() for p in self.agent.model.parameters()),
            "dtype": str(next(self.agent.model.parameters()).dtype).removeprefix("torch."),
            "context_tokens": self.max_len,
            "option_budget_tokens": self.head_max_len,
            "laya_version": laya.__version__,
        }

    def _truncation_warnings(self, state: Any, questions: dict[str, dict[str, Any]]) -> list[str]:
        tok = self.agent.tok
        state_tokens = len(tok(serialize_state(state).replace(tok.mask_token, " "), add_special_tokens=False)["input_ids"])
        internal = {qid: self.agent._to_internal(q) for qid, q in questions.items()}
        warnings = []
        for qid, q in internal.items():
            head, _ = build_sequence(tok, state, q, self.max_len, self.head_max_len, state_ids=[])
            room = max(0, self.max_len - len(head))
            if state_tokens > room:
                warnings.append(f"{qid}: state truncated to {room} of {state_tokens} tokens")
        return warnings

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        questions = {qid: _with_instructions(q) for qid, q in questions.items()}
        result = self.agent.system_one(state, questions)
        result["warnings"] = self._truncation_warnings(state, questions)
        return result


def _with_instructions(q: dict[str, Any]) -> dict[str, Any]:
    """TypeSafe lets a noul carry only criteria; Laya needs instructions, so derive them."""
    if q["type"] != "noul" or q.get("instructions") not in (None, ""):
        return q
    criteria = q.get("criteria") or {}
    claim = criteria.get("true") or f"not: {criteria.get('false')}"
    return {**q, "instructions": f"Is this true: {claim}?"}


def load(model: str, device: str, threads: int | None) -> LayaPredictor:
    if threads:
        torch.set_num_threads(threads)
    return LayaPredictor(model, device)
