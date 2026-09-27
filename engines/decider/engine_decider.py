"""Decider (Mapika): Qwen3.5 fine-tuned to read typed decisions off option-letter logits.

Models: Mapika/decider-0.8b, -2b, -4b. Also reads a stock chat model (for example
Qwen/Qwen3.5-4B) with no decision training at all, which makes a plain-LLM baseline.

On CPU, Decider defaults to bfloat16, which Apple CPUs execute very slowly, so CPU runs use
float32. Qwen3.5's recurrent layers have no fast CPU kernels either way: use MPS on a Mac.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

import torch
from decider.infer import Decider
from decider.prompt import chat_template

STOCK_CHAT_MODELS = {"Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-2B", "Qwen/Qwen3.5-0.8B"}


class DeciderPredictor:
    def __init__(self, model: str, device: str):
        self.model = model
        dtype = torch.float32 if device == "cpu" else None
        self.decider = Decider(model, device=device, dtype=dtype)
        if model in STOCK_CHAT_MODELS:
            self.decider.layout = "chat"
            self.decider.chat = chat_template(self.decider.m.tok)
            self.decider.name = model

    def info(self) -> dict[str, Any]:
        m = self.decider.m
        return {
            "backend": f"torch {torch.__version__}",
            "repo": self.model,
            "params": sum(p.numel() for p in m.parameters()),
            "dtype": str(next(m.parameters()).dtype).removeprefix("torch."),
            "layout": self.decider.layout,
            "decider_model": self.decider.name,
            "temperature": self.decider.T,
            "decider_version": version("decider-ai"),
        }

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return self.decider.system_one(state, questions)


def load(model: str, device: str, threads: int | None) -> DeciderPredictor:
    if threads:
        torch.set_num_threads(threads)
    return DeciderPredictor(model, device)
