"""Jev (TypeSafe AI): the hosted reference model, reached over HTTPS.

Needs TYPESAFE_API_KEY. TYPESAFE_BASE_URL overrides the endpoint. The model id is pinned
(jev-1.13.0 by default) because jev-latest has changed answers between runs. This is the
one engine that sends data off the machine, and its CPU and memory numbers measure the
proxy process, not the model.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.typesafe.ai"
RETRY_STATUSES = {429, 529, 502, 503, 504}
RETRIES = 3


class JevPredictor:
    def __init__(self, model: str, api_key: str, base_url: str, client: httpx.Client | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
        self.headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
        self.available = self._list_models()

    def _list_models(self) -> list[str]:
        r = self.client.get(f"{self.base_url}/v1/models", headers=self.headers)
        if r.status_code == 401:
            raise RuntimeError("TypeSafe rejected the API key (401); create one at https://console.typesafe.ai/settings/keys")
        r.raise_for_status()
        body = r.json()
        items = body.get("models") or body.get("data") or []
        names: list[str] = []
        for m in items:
            name = m.get("name") or m.get("id")
            if name:
                names.append(name)
            names.extend(m.get("aliases") or [])
        return names

    def info(self) -> dict[str, Any]:
        return {"backend": "remote (TypeSafe API)", "endpoint": self.base_url, "remote": True,
                "pinned_model": self.model, "available_models": self.available}

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        payload = {"model": self.model, "state": state, "questions": questions}
        for attempt in range(RETRIES + 1):
            r = self.client.post(f"{self.base_url}/v1/systemone", json=payload, headers=self.headers)
            if r.status_code not in RETRY_STATUSES or attempt == RETRIES:
                break
            time.sleep(0.5 * 2**attempt)
        if r.status_code == 422:
            raise ValueError(f"TypeSafe rejected the request: {_detail(r)}")
        if r.status_code == 401:
            raise RuntimeError("TypeSafe rejected the API key (401)")
        if r.status_code != 200:
            raise RuntimeError(f"TypeSafe returned HTTP {r.status_code}: {_detail(r)}")
        body = r.json()
        return {"answers": body.get("answers"), "usage": body.get("usage") or {}}


def _detail(r: httpx.Response) -> str:
    try:
        body = r.json()
    except ValueError:
        return r.text[:300]
    return str(body.get("detail") or body.get("error") or body)[:300]


def load(model: str, device: str, threads: int | None) -> JevPredictor:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set; see README.md, 'Getting a Jev key'")
    return JevPredictor(model, key, os.environ.get("TYPESAFE_BASE_URL", DEFAULT_BASE_URL))
