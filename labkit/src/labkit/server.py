"""HTTP server that puts any engine behind the lab's /v1/systemone contract.

An engine module exposes one function:

    def load(model: str, device: str, threads: int | None) -> Predictor

where a Predictor has `predict(state, questions) -> {"answers": {...}, "usage": {...}, "warnings"?: [str]}`
(questions in wire form, choice criteria always a map) and `info() -> dict`.

The model loads on a background thread after the port opens, so a supervisor can watch
`/healthz` move from "loading" to "ready" and time each phase. One warm-up request runs
before "ready" because the first call on MPS/MLX compiles kernels. Inference runs one
request at a time on a single worker thread: queueing is part of what a load test measures.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import platform
import sys
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Callable, Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .contract import ContractError, normalise_answers, parse_request

WARMUP_REQUEST = {
    "state": {"subject": "Refund not received", "body": "I cancelled two weeks ago and still have no refund."},
    "questions": {
        "team": {"type": "choice", "instructions": "Which team should handle this?",
                 "criteria": {"billing": "payments and refunds", "support": "product help", "sales": "new purchases"}},
        "urgency": {"type": "score", "instructions": "How urgent is this?",
                    "criteria": ["not urgent", "somewhat urgent", "urgent"]},
        "refund": {"type": "noul", "instructions": "Is the customer asking for a refund?"},
    },
}


class Predictor(Protocol):
    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]: ...
    def info(self) -> dict[str, Any]: ...


LoadFn = Callable[[str, str, "int | None"], Predictor]


def resolve_loader(spec: str) -> LoadFn:
    module_name, _, attr = spec.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr or "load")


class EngineState:
    def __init__(self, engine: str, model: str, device: str, threads: int | None):
        self.engine = engine
        self.model = model
        self.device = device
        self.threads = threads
        self.status = "loading"
        self.error: str | None = None
        self.predictor: Predictor | None = None
        self.load_seconds: float | None = None
        self.warmup_ms: float | None = None
        self.load_warnings: list[str] = []
        self.started = time.time()


def _error(status: int, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message, **extra})


def _describe_validation(e: ValidationError) -> list[str]:
    out = []
    for err in e.errors():
        where = ".".join(str(p) for p in err["loc"] if p not in ("choice", "score", "noul"))
        out.append(f"{where}: {err['msg']}" if where else err["msg"])
    return out


def _run(predictor: Predictor, request: Any) -> tuple[dict[str, Any], dict[str, Any], float]:
    t0 = time.perf_counter()
    result = predictor.predict(request.state, request.wire_questions())
    infer_ms = (time.perf_counter() - t0) * 1000
    if not isinstance(result, dict):
        raise ContractError("predictor returned a non-object")
    answers = normalise_answers(request, result.get("answers"))
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    warnings = [str(w) for w in result.get("warnings") or []]
    return answers, {"raw": result.get("answers"), "usage": usage, "warnings": warnings}, infer_ms


def create_app(state: EngineState, loader: LoadFn) -> FastAPI:
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="infer")

    def load() -> None:
        t0 = time.perf_counter()
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                predictor = loader(state.model, state.device, state.threads)
            state.load_warnings = list(dict.fromkeys(
                f"{w.category.__name__}: {w.message}" for w in caught
                if not issubclass(w.category, (DeprecationWarning, PendingDeprecationWarning, ResourceWarning))))
            state.load_seconds = time.perf_counter() - t0
            state.status = "warming"
            w0 = time.perf_counter()
            _run(predictor, parse_request(WARMUP_REQUEST))
            state.warmup_ms = (time.perf_counter() - w0) * 1000
            state.predictor = predictor
            state.status = "ready"
        except BaseException as e:  # noqa: BLE001 - surfaced verbatim to the supervisor
            state.status = "error"
            state.error = f"{type(e).__name__}: {e}"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        threading.Thread(target=load, name="loader", daemon=True).start()
        try:
            yield
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title=f"lab engine: {state.engine}", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": state.status, "error": state.error,
                "load_seconds": state.load_seconds, "warmup_ms": state.warmup_ms}

    @app.get("/info")
    def info() -> dict[str, Any]:
        details: dict[str, Any] = {}
        if state.predictor is not None:
            try:
                details = state.predictor.info()
            except Exception as e:  # noqa: BLE001
                details = {"info_error": f"{type(e).__name__}: {e}"}
        return {
            "engine": state.engine, "model": state.model, "device": state.device, "threads": state.threads,
            "status": state.status, "error": state.error, "load_seconds": state.load_seconds,
            "warmup_ms": state.warmup_ms, "load_warnings": state.load_warnings, "pid": os.getpid(), "python": sys.version.split()[0],
            "platform": platform.platform(), **details,
        }

    @app.post("/v1/systemone")
    async def systemone(http: Request) -> JSONResponse:
        try:
            body = await http.json()
        except ValueError:
            return _error(400, "request body must be valid JSON")
        try:
            request = parse_request(body)
        except ValidationError as e:
            return _error(422, "invalid request", details=_describe_validation(e))
        if state.status != "ready" or state.predictor is None:
            return _error(503, f"engine is {state.status}", detail=state.error)
        queued = time.perf_counter()
        loop = asyncio.get_running_loop()

        def job() -> tuple[dict[str, Any], dict[str, Any], float, float]:
            queue_ms = (time.perf_counter() - queued) * 1000
            answers, extra, infer_ms = _run(state.predictor, request)
            return answers, extra, infer_ms, queue_ms

        try:
            answers, extra, infer_ms, queue_ms = await loop.run_in_executor(pool, job)
        except ContractError as e:
            return _error(502, f"engine broke the contract: {e}")
        except ValueError as e:
            return _error(422, str(e))
        except Exception as e:  # noqa: BLE001
            return _error(500, f"inference failed: {type(e).__name__}: {e}")
        usage = extra["usage"]
        return JSONResponse(
            content={
                "model": state.model,
                "answers": answers,
                "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": 0},
                "timing": {"infer_ms": infer_ms, "queue_ms": queue_ms},
                "warnings": extra["warnings"],
                "raw_answers": extra["raw"],
            },
            headers={"x-infer-ms": f"{infer_ms:.3f}", "x-queue-ms": f"{queue_ms:.3f}"},
        )

    return app
