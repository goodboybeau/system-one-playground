"""Kev (Jared Palmer): Qwen3.5 base + LoRA + pointer head, shipped as adapters on the Hub.

Models: jaredpalmer/kev-0.8b, -4b, -9b (each pulls its Qwen3.5 base on first load).
Devices: "mlx" runs on the Apple GPU through MLX (Kev's own serving default on Apple
Silicon); "mps" runs the torch path on the Apple GPU; "cpu" runs torch in float32.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import torch
from kev.api import SystemOneRequest
from kev.checkpoint import Checkpoint, LoadOptions
from kev.serve import Server

DEVICES = {"mlx": ("mps", "auto"), "mps": ("mps", "torch"), "cpu": ("cpu", "torch")}


class KevPredictor:
    def __init__(self, model: str, device: str):
        if device not in DEVICES:
            raise ValueError(f"Kev runs on {sorted(DEVICES)}, not {device!r}")
        dev, backend = DEVICES[device]
        opts = replace(LoadOptions.from_env(), backend=backend)
        if dev == "mps":
            opts = replace(opts, attn="sdpa", dtype=torch.bfloat16)
        checkpoint = Checkpoint(model)
        tok, net = checkpoint.load(dev, opts)
        self.server = Server(checkpoint, tok, net, dev)
        self.model = model

    def info(self) -> dict[str, Any]:
        s = self.server
        meta = s.checkpoint.meta
        return {
            "backend": s.model.backend,
            "repo": self.model,
            "base_model": meta.base,
            "dtype": str(s.model.dtype).removeprefix("torch."),
            "temperature": s.model.head.temperature,
            "prefix_cache": {"hits": s.prefix_cache.hits, "misses": s.prefix_cache.misses},
        }

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        request = SystemOneRequest.model_validate({"state": state, "questions": questions, "model": self.model})
        body = self.server.answer(request)
        return {"answers": body["answers"], "usage": {"input_tokens": body["usage"]["input_tokens"]}}


def load(model: str, device: str, threads: int | None) -> KevPredictor:
    if threads:
        torch.set_num_threads(threads)
    return KevPredictor(model, device)
