"""Benchmark engines one at a time across dataset slices, through a running gateway.

    uv run --project gateway python -m gateway.suite [--limit 100] [--datasets a,b] [engine ...]

Each engine is started, run over every dataset, and stopped before the next one starts, so
only one model is resident at a time. Results land in Runs and in the Benchmarks overview.
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx

GATEWAY = "http://127.0.0.1:8080"


def wait_ready(client: httpx.Client, engine: str) -> dict:
    while True:
        run = client.get(f"/api/engines/{engine}").json()["run"]
        if run and run["status"] in ("ready", "error", "exited"):
            return run
        time.sleep(0.5)


def wait_job(client: httpx.Client, job_id: str) -> dict:
    while True:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(1)


def main() -> None:
    p = argparse.ArgumentParser(prog="gateway.suite")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--datasets", default="")
    p.add_argument("engines", nargs="*")
    args = p.parse_args()
    client = httpx.Client(base_url=GATEWAY, timeout=60)
    engines = {e["id"]: e for e in client.get("/api/engines").json()}
    wanted = args.engines or [i for i, e in engines.items() if e["installed"] and not e["remote"]]
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()] or [d["name"] for d in client.get("/api/datasets").json()]
    for engine in wanted:
        label = engines[engine]["label"]
        print(f"\n== {label}", flush=True)
        if engines[engine]["run"]:
            client.post(f"/api/engines/{engine}/stop")
        r = client.post(f"/api/engines/{engine}/start", json={"force": True})
        if r.status_code != 200:
            print(f"   cannot start: {r.json()['error']}")
            continue
        run = wait_ready(client, engine)
        if run["status"] != "ready":
            print(f"   {run['status']}: {run['error']}")
            continue
        try:
            for ds in datasets:
                t0 = time.time()
                r = client.post("/api/bench", json={"dataset": ds, "engines": [engine], "limit": args.limit})
                if r.status_code != 200:
                    print(f"   {ds:18} cannot run: {r.json()['error']}")
                    continue
                job = wait_job(client, r.json()["id"])
                res = (job.get("result") or {}).get("engines", {}).get(engine, {})
                s = res.get("summary")
                if job["status"] != "done" or not s:
                    print(f"   {ds:18} {job['status']}: {job.get('error') or res.get('error')}")
                    continue
                print(f"   {ds:18} acc {s['accuracy']:6.1%}  ece {s['ece'] or 0:.3f}  answered {s['coverage']:4.0%}"
                      f"  p50 {res['latency']['wall']['p50']:7.1f} ms  ({time.time() - t0:5.1f} s)", flush=True)
        except KeyboardInterrupt:
            client.post(f"/api/engines/{engine}/stop")
            sys.exit(130)
        client.post(f"/api/engines/{engine}/stop")


if __name__ == "__main__":
    main()
