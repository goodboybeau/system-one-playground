"""The gateway's HTTP API and the static UI."""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Any, Literal

import psutil
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from labkit import parse_request
from pydantic import BaseModel, Field, ValidationError

from .config import DB_PATH, LOG_DIR, UI_DIST, EngineSpec, load_dotenv, load_registry, missing_weights, weights_on_disk
from .datasets import DatasetError, list_datasets, list_presets, load_items
from .jobs import Jobs
from .scoring import latency_stats
from .store import Store
from .supervisor import EngineError, Supervisor, log_tail

MAX_REPEAT = 50


class StartBody(BaseModel):
    device: str | None = None
    threads: int | None = None
    force: bool = False


class CompareBody(BaseModel):
    request: dict[str, Any]
    engines: list[str] = Field(min_length=1)
    repeat: int = Field(1, ge=1, le=MAX_REPEAT)
    mode: Literal["sequential", "parallel"] = "sequential"


class BenchBody(BaseModel):
    dataset: str
    engines: list[str] = Field(min_length=1)
    limit: int | None = Field(None, ge=1, le=5000)


class LoadBody(BaseModel):
    engine: str
    request: dict[str, Any]
    levels: list[int] = Field(default_factory=lambda: [1, 2, 4, 8])
    per_level: int = Field(32, ge=1, le=500)


def _chip() -> str:
    try:
        return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return platform.processor()


def _validation_details(e: ValidationError) -> list[str]:
    out = []
    for err in e.errors():
        where = ".".join(str(p) for p in err["loc"] if p not in ("choice", "score", "noul"))
        out.append(f"{where}: {err['msg']}" if where else err["msg"])
    return out


def finished_benches(store: Store, dataset: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Finished benchmark runs, newest first, optionally for one dataset slice, with results loaded."""
    out = []
    for r in store.list_runs(limit=5000):
        c = r["config"]
        if r["kind"] != "bench" or r["status"] != "done":
            continue
        if dataset is not None and (c.get("dataset") != dataset or c.get("limit") != limit):
            continue
        full = store.get_run(r["id"])
        if full and full.get("result"):
            out.append(full)
    return out


def merge_latest(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """The newest result per engine across runs of one dataset slice (runs newest first, same items)."""
    merged: dict[str, Any] = {"dataset": {}, "items": [], "engines": {}, "runs": []}
    item_ids: list[str] | None = None
    for r in runs:
        result = r["result"]
        ids = [it["id"] for it in result.get("items", [])]
        if item_ids is None:
            item_ids = ids
            merged["dataset"], merged["items"] = result.get("dataset", {}), result.get("items", [])
        if ids != item_ids:
            continue
        used = False
        for engine, res in result.get("engines", {}).items():
            if engine not in merged["engines"] and res.get("summary"):
                merged["engines"][engine] = {**res, "at": r["created"], "run": r["id"]}
                used = True
        if used:
            merged["runs"].append(r["id"])
    return merged


def create_app(sandbox: bool = True, specs: dict[str, EngineSpec] | None = None, store: Store | None = None) -> FastAPI:
    specs = specs if specs is not None else load_registry()
    store = store or Store(DB_PATH)
    sup = Supervisor(specs, store, sandbox=sandbox)
    jobs = Jobs(sup, store)
    weights: dict[str, int | None] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await sup.start_background()

        def measure() -> None:
            for s in specs.values():
                weights[s.id] = weights_on_disk(s.weights) if s.weights else 0

        asyncio.get_running_loop().run_in_executor(None, measure)
        try:
            yield
        finally:
            for j in list(jobs.jobs.values()):
                if j.task and not j.task.done():
                    j.task.cancel()
            await sup.close()

    app = FastAPI(title="System One Playground", lifespan=lifespan)
    app.state.supervisor, app.state.jobs, app.state.store = sup, jobs, store

    @app.exception_handler(EngineError)
    async def engine_error(_: Request, e: EngineError) -> JSONResponse:
        return JSONResponse(status_code=e.status, content={"error": e.message})

    @app.exception_handler(DatasetError)
    async def dataset_error(_: Request, e: DatasetError) -> JSONResponse:
        return JSONResponse(status_code=404 if "no dataset" in str(e) else 400, content={"error": str(e)})

    @app.exception_handler(RequestValidationError)
    async def invalid_body(_: Request, e: RequestValidationError) -> JSONResponse:
        details = [f"{'.'.join(str(p) for p in err['loc'] if p != 'body')}: {err['msg']}" for err in e.errors()]
        return JSONResponse(status_code=422, content={"error": "invalid request", "details": details})

    @app.exception_handler(ValidationError)
    async def invalid(_: Request, e: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "invalid request", "details": _validation_details(e)})

    def engine_view(spec: EngineSpec) -> dict[str, Any]:
        run = sup.runs.get(spec.id)
        missing = [k for k in spec.secrets if k.endswith("_KEY") and not (load_dotenv().get(k) or os.environ.get(k))]
        return {
            "id": spec.id, "label": spec.label, "model": spec.model, "devices": list(spec.devices),
            "params": spec.params, "architecture": spec.architecture, "license": spec.license, "source": spec.source,
            "note": spec.note, "remote": spec.remote, "installed": spec.installed, "missing_secrets": missing,
            "missing_weights": missing_weights(spec.weights),
            "weights_bytes": weights.get(spec.id), "memory_needed": {d: sup.memory_needed(spec, d) for d in spec.devices},
            "run": run.snapshot() if run else None, "cold_starts": store.cold_starts(spec.id, limit=10),
        }

    @app.get("/api/system")
    def system() -> dict[str, Any]:
        vm = psutil.virtual_memory()
        return {"chip": _chip(), "cores": os.cpu_count(), "physical_cores": psutil.cpu_count(logical=False),
                "memory_total": vm.total, "memory_available": vm.available, "macos": platform.mac_ver()[0],
                "python": platform.python_version(), "sandbox": sandbox, "active_job": jobs.active.snapshot(False) if jobs.active else None}

    @app.get("/api/engines")
    def engines() -> list[dict[str, Any]]:
        return [engine_view(s) for s in specs.values()]

    @app.get("/api/engines/{engine_id}")
    def engine(engine_id: str) -> dict[str, Any]:
        if engine_id not in specs:
            raise EngineError(404, f"unknown engine {engine_id!r}")
        return engine_view(specs[engine_id])

    @app.post("/api/engines/{engine_id}/start")
    async def start(engine_id: str, body: StartBody | None = None) -> dict[str, Any]:
        body = body or StartBody()
        run = await sup.start(engine_id, body.device, body.threads, body.force)
        return run.snapshot()

    @app.post("/api/engines/{engine_id}/stop")
    async def stop(engine_id: str) -> dict[str, Any]:
        await sup.stop(engine_id)
        return {"stopped": engine_id}

    @app.get("/api/engines/{engine_id}/log")
    def log(engine_id: str, lines: int = 200) -> dict[str, Any]:
        if engine_id not in specs:
            raise EngineError(404, f"unknown engine {engine_id!r}")
        return {"log": log_tail(LOG_DIR / f"{engine_id}.log", max(1, min(lines, 2000)))}

    @app.post("/api/compare")
    async def compare(body: CompareBody) -> dict[str, Any]:
        parse_request(body.request)
        engine_ids = list(dict.fromkeys(body.engines))
        for e in engine_ids:
            sup.ready_run(e)

        async def run_engine(e: str) -> dict[str, Any]:
            calls = [await sup.call(e, body.request) for _ in range(body.repeat)]
            first = dict(calls[0])
            ok = [c for c in calls if c["status"] == 200]
            first["repeat"] = {"n": len(calls), "ok": len(ok),
                               "wall": latency_stats([c["wall_ms"] for c in ok]),
                               "infer": latency_stats([c["timing"]["infer_ms"] for c in ok]),
                               "cpu": latency_stats([c["cpu_ms"] for c in ok if c.get("cpu_ms") is not None])}
            run = sup.runs.get(e)
            first["footprint"] = run.samples[-1].footprint if run and run.samples else None
            first["device"] = run.device if run else None
            return first

        t0 = time.time()
        if body.mode == "parallel":
            results = await asyncio.gather(*(run_engine(e) for e in engine_ids))
        else:
            results = [await run_engine(e) for e in engine_ids]
        return {"mode": body.mode, "elapsed_ms": (time.time() - t0) * 1000, "results": results}

    @app.get("/api/metrics")
    def metrics(since: float = 0) -> dict[str, Any]:
        cutoff = max(since, time.time() - 600)
        return {
            "now": time.time(),
            "system": [s.__dict__ for s in sup.system if s.t > cutoff],
            "engines": {i: {"status": r.status, "samples": [s.__dict__ for s in r.samples if s.t > cutoff]}
                        for i, r in sup.runs.items()},
        }

    @app.get("/api/datasets")
    def datasets() -> list[dict[str, Any]]:
        return list_datasets()

    @app.get("/api/datasets/{name}")
    def dataset(name: str, limit: int = 25) -> dict[str, Any]:
        items = load_items(name, max(1, min(limit, 500)))
        return {"name": name, "items": [it.__dict__ for it in items]}

    @app.get("/api/presets")
    def presets() -> list[dict[str, Any]]:
        return list_presets()

    @app.post("/api/bench")
    async def bench(body: BenchBody) -> dict[str, Any]:
        return jobs.start_bench(body.dataset, body.engines, body.limit).snapshot()

    @app.post("/api/loadtest")
    async def loadtest(body: LoadBody) -> dict[str, Any]:
        return jobs.start_loadtest(body.engine, body.request, body.levels, body.per_level).snapshot()

    @app.get("/api/jobs")
    def list_jobs() -> list[dict[str, Any]]:
        return [j.snapshot(False) for j in sorted(jobs.jobs.values(), key=lambda j: -j.created)]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = jobs.jobs.get(job_id)
        if job is None:
            raise EngineError(404, f"no job {job_id}")
        return job.snapshot()

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        return jobs.cancel(job_id).snapshot(False)

    @app.get("/api/report")
    def report(dataset: str, limit: int) -> dict[str, Any]:
        """The newest finished result per engine for one dataset slice, merged into one benchmark result."""
        return merge_latest(finished_benches(store, dataset, limit))

    @app.get("/api/report/overview")
    def overview() -> dict[str, Any]:
        """Accuracy, calibration and latency for every engine on every dataset slice it has been run on."""
        slices: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for r in finished_benches(store):
            slices.setdefault((r["config"]["dataset"], r["config"]["limit"]), []).append(r)
        out = []
        for (ds, n), runs in sorted(slices.items()):
            merged = merge_latest(runs)
            out.append({"dataset": ds, "limit": n, "title": merged["dataset"].get("title", ds), "task": merged["dataset"].get("task"),
                        "engines": {e: {"accuracy": v["summary"]["accuracy"], "ece": v["summary"]["ece"],
                                        "auto_at_95": v["summary"]["auto_at_95"], "p50": v["latency"]["wall"]["p50"],
                                        "at": v["at"]} for e, v in merged["engines"].items()}})
        return {"slices": out}

    @app.get("/api/runs")
    def runs() -> list[dict[str, Any]]:
        live = {j.id for j in jobs.jobs.values() if j.status == "running"}
        return [{**r, "status": r["status"] if r["id"] in live or r["status"] != "running" else "interrupted"}
                for r in store.list_runs()]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        r = store.get_run(run_id)
        if r is None:
            raise EngineError(404, f"no run {run_id}")
        return r

    @app.delete("/api/runs/{run_id}")
    def delete_run(run_id: str) -> dict[str, Any]:
        if jobs.active and jobs.active.id == run_id:
            raise EngineError(409, "cancel the run before deleting it")
        if not store.delete_run(run_id):
            raise EngineError(404, f"no run {run_id}")
        return {"deleted": run_id}

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def api_not_found(path: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": f"no API route /api/{path}"})

    if UI_DIST.exists():
        app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            candidate = (UI_DIST / path).resolve()
            if path and candidate.is_file() and UI_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(UI_DIST / "index.html")

    return app
