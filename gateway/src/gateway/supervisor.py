"""Starts, watches, measures and stops engine processes.

Each local engine runs as `<project>/.venv/bin/python -m labkit.serve ...` inside a macOS
sandbox (sandbox-exec) that denies outbound network and file writes outside a short
allow-list, with HF_HUB_OFFLINE=1 and a minimal environment that carries no secrets.
Remote engines skip the sandbox (they must reach their API) and receive only the env
vars their spec names in `secrets`.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import psutil

from .config import HOME_CACHE, LOG_DIR, RUN_DIR, EngineSpec, load_dotenv, missing_weights
from .procmon import ProcessMeter, ProcSample, SystemSample, system_sample
from .store import Store

SAMPLE_INTERVAL = 0.25
SYSTEM_INTERVAL = 1.0
HISTORY = 2400
STOP_GRACE = 5.0
PIDS_FILE = RUN_DIR / "engines.json"

SANDBOX_PROFILE = """(version 1)
(allow default)
(deny network-outbound)
(allow network-outbound (remote unix-socket))
(allow network-outbound (remote ip "localhost:*"))
(deny file-write*)
(allow file-write*
  (subpath "{project}")
  (subpath "{run_dir}")
  (subpath "{cache}")
  (subpath "/private/var/folders")
  (subpath "/private/tmp")
  (subpath "/dev"))
"""


class EngineError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class EngineRun:
    spec: EngineSpec
    device: str
    threads: int | None
    port: int
    proc: subprocess.Popen
    log_path: Path
    status: str = "starting"
    error: str | None = None
    spawned_at: float = field(default_factory=time.time)
    port_open_at: float | None = None
    ready_at: float | None = None
    load_seconds: float | None = None
    warmup_ms: float | None = None
    info: dict[str, Any] = field(default_factory=dict)
    samples: deque[ProcSample] = field(default_factory=lambda: deque(maxlen=HISTORY))
    peak_footprint: int = 0
    meter: ProcessMeter | None = None
    requests: int = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def snapshot(self) -> dict[str, Any]:
        last = self.samples[-1] if self.samples else None
        return {
            "id": self.spec.id, "device": self.device, "threads": self.threads, "port": self.port,
            "pid": self.proc.pid, "status": self.status, "error": self.error,
            "spawned_at": self.spawned_at, "ready_at": self.ready_at,
            "cold_start": {
                "process_s": (self.port_open_at - self.spawned_at) if self.port_open_at else None,
                "load_s": self.load_seconds, "warmup_ms": self.warmup_ms,
                "total_s": (self.ready_at - self.spawned_at) if self.ready_at else None,
            },
            "info": self.info, "requests": self.requests,
            "cpu_percent": last.cpu_percent if last else None,
            "footprint": last.footprint if last else None, "rss": last.rss if last else None,
            "threads_os": last.threads if last else None, "peak_footprint": self.peak_footprint,
        }


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def log_tail(path: Path, lines: int = 25) -> str:
    try:
        text = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    noise = ("Fetching ", "Loading weights", "Warning: You are sending unauthenticated")
    return "\n".join([line for line in text if not line.startswith(noise)][-lines:])


class Supervisor:
    def __init__(self, specs: dict[str, EngineSpec], store: Store, sandbox: bool = True):
        self.specs = specs
        self.store = store
        self.sandbox = sandbox
        self.runs: dict[str, EngineRun] = {}
        self.system: deque[SystemSample] = deque(maxlen=HISTORY // 4)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=5.0))
        self._tasks: list[asyncio.Task] = []
        self._locks: dict[str, asyncio.Lock] = {}

    async def start_background(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.kill_orphans()
        psutil.cpu_percent(interval=None)
        self._tasks.append(asyncio.create_task(self._sample_loop(), name="sampler"))

    async def close(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await asyncio.gather(*(self.stop(i) for i in list(self.runs)), return_exceptions=True)
        await self.client.aclose()

    def _lock(self, engine_id: str) -> asyncio.Lock:
        return self._locks.setdefault(engine_id, asyncio.Lock())

    def kill_orphans(self) -> None:
        """Stop engines a previous gateway left running (it crashed or was killed)."""
        if not PIDS_FILE.exists():
            return
        try:
            pids = json.loads(PIDS_FILE.read_text())
        except ValueError:
            pids = {}
        for pid in pids.values():
            try:
                p = psutil.Process(int(pid))
                if "labkit.serve" in " ".join(p.cmdline()):
                    os.killpg(p.pid, signal.SIGKILL)
            except (psutil.Error, ProcessLookupError, PermissionError, ValueError):
                pass
        PIDS_FILE.unlink(missing_ok=True)

    def _write_pids(self) -> None:
        PIDS_FILE.write_text(json.dumps({i: r.proc.pid for i, r in self.runs.items() if r.alive}))

    def memory_needed(self, spec: EngineSpec, device: str) -> int:
        seen = self.store.peak_footprint(spec.id, device)
        return seen or spec.memory_estimate(device)

    def _env(self, spec: EngineSpec, tmp: Path) -> dict[str, str]:
        env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(Path.home()), "LANG": "en_US.UTF-8",
            "PYTHONPATH": str(spec.project), "PYTHONUNBUFFERED": "1", "TMPDIR": str(tmp),
            "TOKENIZERS_PARALLELISM": "false", "HF_HUB_DISABLE_TELEMETRY": "1",
        }
        if spec.remote:
            secrets = load_dotenv()
            env.update({k: secrets.get(k) or os.environ[k] for k in spec.secrets if secrets.get(k) or os.environ.get(k)})
        else:
            env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
        return env

    def _command(self, spec: EngineSpec, device: str, threads: int | None, port: int) -> list[str]:
        cmd = [str(spec.python), "-m", "labkit.serve", "--engine", spec.loader, "--model", spec.model,
               "--device", device, "--port", str(port), "--exit-with-parent"]
        if threads:
            cmd += ["--threads", str(threads)]
        if self.sandbox and not spec.remote:
            profile = RUN_DIR / "sandbox" / f"{spec.id}.sb"
            profile.parent.mkdir(parents=True, exist_ok=True)
            profile.write_text(SANDBOX_PROFILE.format(project=spec.project, run_dir=RUN_DIR, cache=HOME_CACHE))
            cmd = ["/usr/bin/sandbox-exec", "-f", str(profile), *cmd]
        return cmd

    async def start(self, engine_id: str, device: str | None = None, threads: int | None = None,
                    force: bool = False) -> EngineRun:
        spec = self.specs.get(engine_id)
        if spec is None:
            raise EngineError(404, f"unknown engine {engine_id!r}")
        device = device or spec.devices[0]
        if device not in spec.devices:
            raise EngineError(400, f"{spec.label} runs on {', '.join(spec.devices)}, not {device}")
        if threads is not None and not 1 <= threads <= (os.cpu_count() or 64):
            raise EngineError(400, f"threads must be between 1 and {os.cpu_count()}")
        if not spec.installed:
            raise EngineError(409, f"{spec.label} is not installed: run `make setup`")
        if missing := missing_weights(spec.weights):
            raise EngineError(409, f"{spec.label} needs weights that aren't downloaded ({', '.join(missing)}): run `make weights-all`")
        async with self._lock(engine_id):
            existing = self.runs.get(engine_id)
            if existing and existing.alive:
                raise EngineError(409, f"{spec.label} is already running")
            available = psutil.virtual_memory().available
            needed = self.memory_needed(spec, device)
            if needed > available and not force:
                raise EngineError(507, f"{spec.label} needs about {needed / 2**30:.1f} GB and "
                                       f"{available / 2**30:.1f} GB is free. Stop another engine or start anyway.")
            port = free_port()
            tmp = RUN_DIR / "tmp" / spec.id
            tmp.mkdir(parents=True, exist_ok=True)
            log_path = LOG_DIR / f"{spec.id}.log"
            with log_path.open("a") as log:
                log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start {spec.id} on {device} port {port}\n")
                log.flush()
                proc = subprocess.Popen(self._command(spec, device, threads, port), cwd=spec.project,
                                        env=self._env(spec, tmp), stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, start_new_session=True)
            run = EngineRun(spec=spec, device=device, threads=threads, port=port, proc=proc, log_path=log_path)
            try:
                run.meter = ProcessMeter(proc.pid)
            except psutil.Error:
                pass
            self.runs[engine_id] = run
            self._write_pids()
            self._tasks.append(asyncio.create_task(self._watch(run), name=f"watch-{engine_id}"))
            return run

    async def _watch(self, run: EngineRun) -> None:
        while run.status in ("starting", "loading", "warming"):
            if not run.alive:
                self._mark_exited(run)
                return
            try:
                h = (await self.client.get(run.url + "/healthz", timeout=2.0)).json()
            except (httpx.HTTPError, ValueError):
                await asyncio.sleep(0.1)
                continue
            if run.status not in ("starting", "loading", "warming"):
                return
            if run.port_open_at is None:
                run.port_open_at = time.time()
            run.load_seconds, run.warmup_ms = h.get("load_seconds"), h.get("warmup_ms")
            if h["status"] == "error":
                run.error = h.get("error")
                run.status = "error"
                return
            if h["status"] == "ready":
                run.ready_at = time.time()
                try:
                    run.info = (await self.client.get(run.url + "/info", timeout=5.0)).json()
                except (httpx.HTTPError, ValueError):
                    pass
                run.status = "ready"
                self.store.record_cold_start(run.spec.id, run.device, run.snapshot()["cold_start"],
                                             run.samples[-1].footprint if run.samples else None)
                return
            run.status = h["status"]
            await asyncio.sleep(0.2)

    def _mark_exited(self, run: EngineRun) -> None:
        if run.status in ("stopping", "stopped"):
            return
        code = run.proc.returncode
        run.status = "exited"
        run.error = f"process exited with code {code}\n{log_tail(run.log_path)}"

    async def stop(self, engine_id: str) -> None:
        run = self.runs.get(engine_id)
        if run is None:
            raise EngineError(404, f"{engine_id} is not running")
        async with self._lock(engine_id):
            run.status = "stopping"
            if run.alive:
                try:
                    os.killpg(run.proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.to_thread(run.proc.wait, STOP_GRACE)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(run.proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await asyncio.to_thread(run.proc.wait)
            run.status = "stopped"
            if run.peak_footprint:
                self.store.record_peak(run.spec.id, run.device, run.peak_footprint)
            self.runs.pop(engine_id, None)
            self._write_pids()

    async def _sample_loop(self) -> None:
        next_system = 0.0
        while True:
            now = time.monotonic()
            if now >= next_system:
                self.system.append(await asyncio.to_thread(system_sample))
                next_system = now + SYSTEM_INTERVAL
            for run in list(self.runs.values()):
                if run.meter is None or run.status in ("stopping", "stopped"):
                    continue
                if not run.alive:
                    self._mark_exited(run)
                    continue
                s = run.meter.sample()
                if s is not None:
                    run.samples.append(s)
                    run.peak_footprint = max(run.peak_footprint, s.footprint)
            await asyncio.sleep(SAMPLE_INTERVAL)

    def ready_run(self, engine_id: str) -> EngineRun:
        run = self.runs.get(engine_id)
        if run is None:
            raise EngineError(409, f"{engine_id} is not running")
        if run.status != "ready":
            raise EngineError(409, f"{engine_id} is {run.status}")
        return run

    @staticmethod
    def _cpu_seconds(run: EngineRun) -> float | None:
        if run.meter is None:
            return None
        try:
            return run.meter.cpu_seconds()
        except psutil.Error:
            return None

    async def call(self, engine_id: str, body: Any) -> dict[str, Any]:
        """One /v1/systemone request, with wall time and the CPU time the engine spent on it."""
        run = self.ready_run(engine_id)
        cpu0 = self._cpu_seconds(run)
        t0 = time.perf_counter()
        try:
            r = await self.client.post(run.url + "/v1/systemone", json=body)
        except httpx.HTTPError as e:
            if not run.alive:
                self._mark_exited(run)
            return {"engine": engine_id, "status": 0, "error": f"{type(e).__name__}: {e}",
                    "wall_ms": (time.perf_counter() - t0) * 1000}
        wall_ms = (time.perf_counter() - t0) * 1000
        cpu1 = self._cpu_seconds(run)
        run.requests += 1
        try:
            payload = r.json()
        except ValueError:
            payload = {"error": r.text[:500]}
        out = {"engine": engine_id, "status": r.status_code, "wall_ms": wall_ms,
               "cpu_ms": (cpu1 - cpu0) * 1000 if cpu0 is not None and cpu1 is not None else None}
        if r.status_code == 200:
            out.update(payload)
        else:
            out["error"] = payload.get("error") or str(payload)
            if payload.get("details"):
                out["details"] = payload["details"]
        return out
