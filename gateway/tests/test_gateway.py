import signal
import time
from pathlib import Path

import psutil
import pytest
from conftest import BODY, start_ready, wait_for


def test_lists_engines_and_system(lab):
    engines = {e["id"]: e for e in lab.get("/api/engines").json()}
    assert {"fast", "slow", "huge"} <= set(engines)
    assert engines["fast"]["installed"] and engines["fast"]["run"] is None
    s = lab.get("/api/system").json()
    assert s["cores"] > 0 and s["memory_total"] > 0 and s["sandbox"] is True


def test_start_measures_cold_start_and_resources(lab):
    e = start_ready(lab, "fast")
    run = e["run"]
    assert run["status"] == "ready", run
    cold = run["cold_start"]
    assert cold["process_s"] > 0 and cold["load_s"] >= 0 and cold["warmup_ms"] >= 0 and cold["total_s"] >= cold["process_s"]
    wait_for(lambda: lab.get("/api/engines/fast").json()["run"]["footprint"])
    run = lab.get("/api/engines/fast").json()["run"]
    assert run["footprint"] > 1_000_000 and run["peak_footprint"] >= run["footprint"]
    assert run["info"]["backend"] == "mock" and run["info"]["pid"] == run["pid"]
    assert lab.get("/api/engines/fast").json()["cold_starts"][0]["total_s"] > 0


def test_start_errors(lab):
    assert lab.post("/api/engines/nope/start").status_code == 404
    assert lab.post("/api/engines/fast/start", json={"device": "tpu"}).status_code == 400
    assert lab.post("/api/engines/fast/start", json={"threads": 0}).status_code == 400
    start_ready(lab, "fast")
    r = lab.post("/api/engines/fast/start")
    assert r.status_code == 409 and "already running" in r.json()["error"]


def test_memory_guard(lab):
    r = lab.post("/api/engines/huge/start")
    assert r.status_code == 507 and "GB" in r.json()["error"]
    e = start_ready(lab, "huge", force=True)
    assert e["run"]["status"] == "ready"


def test_load_failure_and_crash_are_reported(lab):
    e = start_ready(lab, "failload")
    assert e["run"]["status"] == "error" and "fail while loading" in e["run"]["error"]
    e = start_ready(lab, "exitload")
    assert e["run"]["status"] == "exited" and "code 3" in e["run"]["error"]


def test_sandbox_blocks_network(lab):
    e = start_ready(lab, "probe")
    assert e["run"]["status"] == "ready"
    assert e["run"]["info"]["network"].startswith("blocked"), e["run"]["info"]


def test_engines_get_no_secrets(lab, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-should-not-leak")
    e = start_ready(lab, "fast")
    env = psutil.Process(e["run"]["pid"]).environ()
    assert "TYPESAFE_API_KEY" not in env
    assert env["HF_HUB_OFFLINE"] == "1"


def test_stop_kills_the_process(lab):
    e = start_ready(lab, "fast")
    pid = e["run"]["pid"]
    assert lab.post("/api/engines/fast/stop").status_code == 200
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert lab.get("/api/engines/fast").json()["run"] is None
    assert lab.post("/api/engines/fast/stop").status_code == 404


def test_externally_killed_engine_is_marked_exited(lab):
    e = start_ready(lab, "fast")
    psutil.Process(e["run"]["pid"]).send_signal(signal.SIGKILL)
    run = wait_for(lambda: (r := lab.get("/api/engines/fast").json()["run"]) and r["status"] == "exited" and r)
    assert "exited with code" in run["error"]
    assert lab.post("/api/compare", json={"request": BODY, "engines": ["fast"]}).status_code == 409


def test_compare_sequential_and_parallel(lab):
    start_ready(lab, "fast")
    start_ready(lab, "slow")
    for mode in ("sequential", "parallel"):
        r = lab.post("/api/compare", json={"request": BODY, "engines": ["fast", "slow"], "repeat": 3, "mode": mode})
        assert r.status_code == 200, r.text
        res = {x["engine"]: x for x in r.json()["results"]}
        assert res["fast"]["answers"]["team"]["choice"] == "billing"
        assert res["slow"]["repeat"]["n"] == 3 and res["slow"]["repeat"]["wall"]["p50"] >= 60
        assert res["fast"]["cpu_ms"] is not None and res["fast"]["footprint"] is None or res["fast"]["footprint"] > 0


def test_compare_rejects_bad_requests(lab):
    start_ready(lab, "fast")
    r = lab.post("/api/compare", json={"request": {"state": "x", "questions": {"q": {"type": "score", "criteria": ["a"]}}},
                                       "engines": ["fast"]})
    assert r.status_code == 422 and any("2-10 levels" in d for d in r.json()["details"])
    r = lab.post("/api/compare", json={"request": BODY, "engines": []})
    assert r.status_code == 422
    r = lab.post("/api/compare", json={"request": BODY, "engines": ["slow"]})
    assert r.status_code == 409 and "not running" in r.json()["error"]


def test_metrics_stream_has_samples(lab):
    start_ready(lab, "fast")
    m = wait_for(lambda: (x := lab.get("/api/metrics").json())["engines"].get("fast", {}).get("samples") and x)
    s = m["engines"]["fast"]["samples"][-1]
    assert {"cpu_percent", "footprint", "rss", "cpu_seconds", "threads"} <= set(s)
    assert wait_for(lambda: lab.get("/api/metrics").json()["system"])[0]["memory_total"] > 0
    later = lab.get("/api/metrics", params={"since": time.time() + 100}).json()
    assert later["system"] == [] and later["engines"]["fast"]["samples"] == []


def test_benchmark_job(lab):
    start_ready(lab, "fast")
    r = lab.post("/api/bench", json={"dataset": "tiny", "engines": ["fast"]})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    job = wait_for(lambda: (j := lab.get(f"/api/jobs/{job_id}").json())["status"] != "running" and j)
    assert job["status"] == "done", job
    res = job["result"]["engines"]["fast"]
    assert res["summary"]["items"] == 4 and res["summary"]["accuracy"] == 0.75
    assert res["summary"]["confusion"]["labels"] == ["billing", "technical"]
    assert res["latency"]["wall"]["n"] == 4 and len(res["answers"]) == 4
    run = lab.get(f"/api/runs/{job_id}").json()
    assert run["status"] == "done" and run["result"]["engines"]["fast"]["summary"]["accuracy"] == 0.75
    assert lab.get("/api/runs").json()[0]["id"] == job_id
    assert lab.delete(f"/api/runs/{job_id}").status_code == 200
    assert lab.get(f"/api/runs/{job_id}").status_code == 404


def test_benchmark_validation(lab):
    assert lab.post("/api/bench", json={"dataset": "nope", "engines": ["fast"]}).status_code == 404
    assert lab.post("/api/bench", json={"dataset": "../etc", "engines": ["fast"]}).status_code in (400, 404)
    assert lab.post("/api/bench", json={"dataset": "tiny", "engines": ["fast"]}).status_code == 409


def test_one_job_at_a_time_and_cancel(lab):
    start_ready(lab, "slow")
    body = {"engine": "slow", "request": BODY, "levels": [1], "per_level": 200}
    job_id = lab.post("/api/loadtest", json=body).json()["id"]
    awake = wait_for(lambda: [p for p in psutil.Process().children(recursive=True) if p.name() == "caffeinate"])
    r = lab.post("/api/bench", json={"dataset": "tiny", "engines": ["slow"]})
    assert r.status_code == 409 and "already running" in r.json()["error"]
    assert lab.post(f"/api/jobs/{job_id}/cancel").status_code == 200
    job = wait_for(lambda: (j := lab.get(f"/api/jobs/{job_id}").json())["status"] != "running" and j)
    assert job["status"] == "cancelled"
    assert job["progress"]["done"] < 200
    wait_for(lambda: not any(p.is_running() and p.status() != psutil.STATUS_ZOMBIE for p in awake))


def test_load_test_measures_queueing(lab):
    start_ready(lab, "slow")
    body = {"engine": "slow", "request": BODY, "levels": [1, 4], "per_level": 8}
    job_id = lab.post("/api/loadtest", json=body).json()["id"]
    job = wait_for(lambda: (j := lab.get(f"/api/jobs/{job_id}").json())["status"] != "running" and j, timeout=60)
    assert job["status"] == "done", job
    one, four = job["result"]["levels"]
    assert one["concurrency"] == 1 and four["concurrency"] == 4 and one["ok"] == four["ok"] == 8
    assert one["throughput_rps"] == pytest.approx(four["throughput_rps"], rel=0.35)
    assert four["latency"]["p50"] > 2 * one["latency"]["p50"]
    assert four["queue"]["max"] > 100


def test_load_test_validation(lab):
    start_ready(lab, "fast")
    for bad in ({"levels": [0]}, {"levels": [65]}, {"per_level": 0}, {"levels": [1, 2, 4, 8, 16], "per_level": 500}):
        body = {"engine": "fast", "request": BODY, **bad}
        assert lab.post("/api/loadtest", json=body).status_code in (400, 422), bad


def test_datasets_and_presets(lab):
    ds = lab.get("/api/datasets").json()
    assert ds[0]["name"] == "tiny" and ds[0]["items"] == 4
    assert len(lab.get("/api/datasets/tiny", params={"limit": 2}).json()["items"]) == 2
    assert lab.get("/api/presets").json()[0]["id"] == "triage"


def test_unknown_api_route_is_json_404(lab):
    r = lab.get("/api/nothing/here")
    assert r.status_code == 404 and r.json()["error"]


def test_orphans_are_killed_on_startup(lab):
    from gateway.store import Store
    from gateway.supervisor import Supervisor

    e = start_ready(lab, "fast")
    pid = e["run"]["pid"]
    sup = Supervisor({}, Store(Path("/tmp") / f"orphan-{time.time_ns()}.db"))
    sup.kill_orphans()
    wait_for(lambda: not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE)


def test_stop_while_loading(lab):
    r = lab.post("/api/engines/slowload/start")
    assert r.status_code == 200
    assert lab.post("/api/engines/slowload/stop").status_code == 200
    time.sleep(1.0)
    assert lab.get("/api/engines/slowload").json()["run"] is None
    e = start_ready(lab, "slowload")
    assert e["run"]["status"] == "ready"


def test_report_merges_latest_result_per_engine(lab):
    start_ready(lab, "fast")
    start_ready(lab, "slow")
    ids = []
    for engine in ("fast", "slow", "fast"):
        job_id = lab.post("/api/bench", json={"dataset": "tiny", "engines": [engine], "limit": 4}).json()["id"]
        wait_for(lambda: lab.get(f"/api/jobs/{job_id}").json()["status"] == "done")
        ids.append(job_id)
    rep = lab.get("/api/report", params={"dataset": "tiny", "limit": 4}).json()
    assert set(rep["engines"]) == {"fast", "slow"}
    assert rep["engines"]["fast"]["run"] == ids[2] and rep["engines"]["slow"]["run"] == ids[1]
    assert len(rep["items"]) == 4 and rep["dataset"]["title"] == "Tiny"
    ov = lab.get("/api/report/overview").json()["slices"]
    tiny = next(s for s in ov if s["dataset"] == "tiny" and s["limit"] == 4)
    assert tiny["engines"]["fast"]["accuracy"] == 0.75
    empty = lab.get("/api/report", params={"dataset": "tiny", "limit": 3}).json()
    assert empty["engines"] == {}


def test_engines_die_with_a_killed_gateway(tmp_path):
    import os
    import subprocess
    import sys

    code = f"""
import asyncio, sys
sys.path.insert(0, {str(Path(__file__).parent)!r})
from gateway.config import load_registry
from gateway.store import Store
from gateway.supervisor import Supervisor
async def main():
    sup = Supervisor(load_registry(), Store(__import__('pathlib').Path({str(tmp_path)!r}) / 'db'))
    await sup.start_background()
    run = await sup.start('fast')
    print(run.proc.pid, flush=True)
    await asyncio.sleep(3600)
asyncio.run(main())
"""
    gw = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, env=os.environ)
    engine_pid = int(gw.stdout.readline())
    assert psutil.pid_exists(engine_pid)
    time.sleep(1.5)
    gw.kill()
    gw.wait()
    wait_for(lambda: not psutil.pid_exists(engine_pid) or psutil.Process(engine_pid).status() == psutil.STATUS_ZOMBIE, timeout=10)


def test_engine_without_weights_cannot_start(lab, monkeypatch):
    from gateway import supervisor

    monkeypatch.setattr(supervisor, "missing_weights", lambda repos: ["org/model"])
    r = lab.post("/api/engines/fast/start")
    assert r.status_code == 409 and "make weights-all" in r.json()["error"]


def test_missing_weights_are_reported(tmp_path, monkeypatch):
    from gateway import config

    monkeypatch.setattr(config, "HF_CACHE", tmp_path)
    assert config.missing_weights(("org/a", "org/a:sub", "org/b")) == ["org/a", "org/b"]
    (tmp_path / "models--org--a" / "snapshots" / "abc").mkdir(parents=True)
    assert config.missing_weights(("org/a:sub", "org/b")) == ["org/b"]
