"""Long-running measurements: dataset benchmarks and load tests.

One job runs at a time, so jobs never compete for CPU, GPU or memory with each other.
Within a benchmark, engines run one after another for the same reason.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from labkit import parse_request

from .datasets import Item, list_datasets, load_items
from .scoring import Scored, latency_stats, score_item, summarise
from .store import Store
from .supervisor import EngineError, EngineRun, Supervisor

MAX_LOAD_REQUESTS = 2000
MAX_CONCURRENCY = 64


@dataclass
class Job:
    id: str
    kind: str
    title: str
    config: dict[str, Any]
    status: str = "running"
    created: float = field(default_factory=time.time)
    finished: float | None = None
    progress: dict[str, Any] = field(default_factory=lambda: {"done": 0, "total": 0, "engine": None})
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    cancelled: bool = False
    task: asyncio.Task | None = None

    def snapshot(self, with_result: bool = True) -> dict[str, Any]:
        out = {"id": self.id, "kind": self.kind, "title": self.title, "config": self.config, "status": self.status,
               "created": self.created, "finished": self.finished, "progress": self.progress, "error": self.error}
        if with_result:
            out["result"] = self.result
        return out


def resources(run: EngineRun, t0: float, t1: float) -> dict[str, Any]:
    """CPU and memory over [t0, t1]. Samples arrive every 250 ms, so a window shorter than that is
    widened to the nearest sample on each side rather than reported empty."""
    samples = list(run.samples)
    window = [s for s in samples if t0 <= s.t <= t1]
    if not window:
        before = [s for s in samples if s.t < t0][-1:]
        after = [s for s in samples if s.t > t1][:1]
        window = before + after
    if not window:
        return {"samples": 0}
    return {"samples": len(window),
            "cpu_avg": sum(s.cpu_percent for s in window) / len(window),
            "cpu_peak": max(s.cpu_percent for s in window),
            "footprint_peak": max(s.footprint for s in window),
            "footprint_start": window[0].footprint}


def keep_awake() -> subprocess.Popen | None:
    """Hold off idle sleep while a job runs: a Mac that sleeps mid-benchmark freezes every clock we measure with."""
    try:
        return subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None


class Jobs:
    def __init__(self, supervisor: Supervisor, store: Store):
        self.sup = supervisor
        self.store = store
        self.jobs: dict[str, Job] = {}

    @property
    def active(self) -> Job | None:
        return next((j for j in self.jobs.values() if j.status == "running"), None)

    def _launch(self, kind: str, title: str, config: dict[str, Any], body: Callable[[Job], Awaitable[None]]) -> Job:
        if (busy := self.active) is not None:
            raise EngineError(409, f"a {busy.kind} is already running ({busy.title}); wait for it or cancel it")
        job = Job(id=uuid.uuid4().hex[:10], kind=kind, title=title, config=config)
        self.jobs[job.id] = job
        self.store.save_run(job.id, kind, title, job.created, "running", config, None, None)

        async def runner() -> None:
            awake = keep_awake()
            try:
                await body(job)
                job.status = "cancelled" if job.cancelled else "done"
            except asyncio.CancelledError:
                job.status = "cancelled"
            except Exception as e:  # noqa: BLE001 - reported to the UI
                job.status, job.error = "error", f"{type(e).__name__}: {e}"
            finally:
                if awake is not None:
                    awake.terminate()
            job.finished = time.time()
            self.store.save_run(job.id, kind, title, job.created, job.status, config,
                                {**job.result, "error": job.error}, job.finished)

        job.task = asyncio.create_task(runner(), name=f"job-{job.id}")
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise EngineError(404, f"no job {job_id}")
        job.cancelled = True
        return job

    def _require_ready(self, engines: list[str]) -> None:
        if not engines:
            raise EngineError(400, "pick at least one engine")
        for e in engines:
            self.sup.ready_run(e)

    # ------------------------------------------------------------------ benchmark
    def start_bench(self, dataset: str, engines: list[str], limit: int | None) -> Job:
        meta = next((d for d in list_datasets() if d["name"] == dataset), None)
        if meta is None:
            raise EngineError(404, f"no dataset named {dataset!r}")
        items = load_items(dataset, limit)
        engines = list(dict.fromkeys(engines))
        self._require_ready(engines)
        config = {"dataset": dataset, "engines": engines, "limit": len(items)}
        title = f"{meta['title']} × {', '.join(self.sup.specs[e].label for e in engines)}"
        return self._launch("bench", title, config, lambda job: self._bench(job, meta, items, engines))

    async def _bench(self, job: Job, meta: dict[str, Any], items: list[Item], engines: list[str]) -> None:
        job.progress = {"done": 0, "total": len(items) * len(engines), "engine": None}
        job.result = {"dataset": meta, "items": [{"id": it.id, "gold": it.gold, "lang": it.lang,
                                                   "state": it.state if isinstance(it.state, str) else it.state}
                                                  for it in items], "engines": {}}
        for engine in engines:
            if job.cancelled:
                return
            job.progress["engine"] = engine
            try:
                run = self.sup.ready_run(engine)
            except EngineError as e:
                job.result["engines"][engine] = {"error": e.message}
                job.progress["done"] += len(items)
                continue
            job.result["engines"][engine] = await self._bench_engine(job, run, meta, items)

    async def _bench_engine(self, job: Job, run: EngineRun, meta: dict[str, Any], items: list[Item]) -> dict[str, Any]:
        engine = run.spec.id
        answers: list[dict[str, Any]] = []
        scored: list[Scored] = []
        by_lang: dict[str, list[bool]] = {}
        errors: dict[str, int] = {}
        warned = 0
        walls, infers, cpus = [], [], []
        t0 = time.time()
        for it in items:
            if job.cancelled:
                break
            r = await self.sup.call(engine, it.request())
            job.progress["done"] += 1
            row: dict[str, Any] = {"wall_ms": r["wall_ms"]}
            walls.append(r["wall_ms"])
            if r["status"] != 200:
                msg = (r.get("error") or "error").split("\n")[0][:200]
                errors[msg] = errors.get(msg, 0) + 1
                row["error"] = msg
                if it.lang:
                    by_lang.setdefault(it.lang, []).append(False)
                answers.append(row)
                continue
            a = r["answers"]["q"]
            s = score_item(it.question, it.gold, a)
            scored.append(s)
            infers.append(r["timing"]["infer_ms"])
            if r.get("cpu_ms") is not None:
                cpus.append(r["cpu_ms"])
            if r.get("warnings"):
                warned += 1
            if it.lang:
                by_lang.setdefault(it.lang, []).append(s.correct)
            top = sorted(a.get("probabilities", {}).items(), key=lambda kv: -kv[1])[:3]
            row.update({"predicted": s.predicted, "correct": s.correct, "p_top": s.p_top, "top": top,
                        "warnings": r.get("warnings") or [], **({"noul": a["noul"]} if "noul" in a else {}),
                        **({"score": a["score"]} if "score" in a else {})})
            answers.append(row)
        t1 = time.time()
        labels = meta.get("labels")
        return {
            "device": run.device, "info": run.info, "answers": answers,
            "summary": summarise(scored, total=len(answers), labels=labels),
            "by_lang": {lang: sum(v) / len(v) for lang, v in sorted(by_lang.items())} if by_lang else None,
            "latency": {"wall": latency_stats(walls), "infer": latency_stats(infers)},
            "cpu_ms": latency_stats(cpus), "errors": errors, "truncated": warned,
            "elapsed_s": t1 - t0, "resources": resources(run, t0, t1),
        }

    # ------------------------------------------------------------------ load test
    def start_loadtest(self, engine: str, request: dict[str, Any], levels: list[int], per_level: int) -> Job:
        parse_request(request)
        self._require_ready([engine])
        levels = sorted(set(levels))
        if not levels or any(not 1 <= c <= MAX_CONCURRENCY for c in levels):
            raise EngineError(400, f"concurrency levels must be between 1 and {MAX_CONCURRENCY}")
        if not 1 <= per_level or per_level * len(levels) > MAX_LOAD_REQUESTS:
            raise EngineError(400, f"at most {MAX_LOAD_REQUESTS} requests per load test")
        config = {"engine": engine, "levels": levels, "per_level": per_level, "request": request}
        title = f"{self.sup.specs[engine].label} at {', '.join(map(str, levels))} concurrent"
        return self._launch("loadtest", title, config, lambda job: self._loadtest(job, engine, request, levels, per_level))

    async def _loadtest(self, job: Job, engine: str, request: dict[str, Any], levels: list[int], per_level: int) -> None:
        run = self.sup.ready_run(engine)
        job.progress = {"done": 0, "total": per_level * len(levels), "engine": engine}
        job.result = {"engine": engine, "device": run.device, "levels": []}
        for _ in range(2):
            await self.sup.call(engine, request)
        for c in levels:
            if job.cancelled:
                return
            sem = asyncio.Semaphore(c)
            results: list[dict[str, Any]] = []

            async def one() -> None:
                async with sem:
                    if job.cancelled:
                        return
                    results.append(await self.sup.call(engine, request))
                    job.progress["done"] += 1

            t0 = time.time()
            await asyncio.gather(*(one() for _ in range(per_level)))
            t1 = time.time()
            ok = [r for r in results if r["status"] == 200]
            job.result["levels"].append({
                "concurrency": c, "requests": len(results), "ok": len(ok), "errors": len(results) - len(ok),
                "elapsed_s": t1 - t0, "throughput_rps": len(ok) / (t1 - t0) if t1 > t0 else None,
                "latency": latency_stats([r["wall_ms"] for r in ok]),
                "queue": latency_stats([r["timing"]["queue_ms"] for r in ok]),
                "resources": resources(run, t0, t1),
            })
