"""Start each engine through a running gateway, run the conformance suite against it, stop it.

    uv run --project gateway python -m gateway.verify [engine ...]   (default: every installed local engine)
"""

from __future__ import annotations

import sys
import time

import httpx
from labkit.conformance import run as conformance

GATEWAY = "http://127.0.0.1:8080"


def main() -> None:
    client = httpx.Client(base_url=GATEWAY, timeout=60)
    engines = {e["id"]: e for e in client.get("/api/engines").json()}
    wanted = sys.argv[1:] or [i for i, e in engines.items() if e["installed"] and not e["remote"]]
    failures = 0
    for engine_id in wanted:
        e = engines[engine_id]
        print(f"\n== {e['label']} ({engine_id})", flush=True)
        if e["run"]:
            client.post(f"/api/engines/{engine_id}/stop")
        r = client.post(f"/api/engines/{engine_id}/start", json={"force": True})
        if r.status_code != 200:
            print(f"   cannot start: {r.json()['error']}")
            failures += 1
            continue
        deadline = time.time() + 900
        while time.time() < deadline:
            run = client.get(f"/api/engines/{engine_id}").json()["run"]
            if run["status"] in ("ready", "error", "exited"):
                break
            time.sleep(0.5)
        if run["status"] != "ready":
            print(f"   {run['status']}: {run['error']}")
            failures += 1
            continue
        results = conformance(f"http://127.0.0.1:{run['port']}")
        time.sleep(0.6)
        run = client.get(f"/api/engines/{engine_id}").json()["run"]
        bad = [(n, err) for n, err in results if err]
        cold = run["cold_start"]
        print(f"   conformance {len(results) - len(bad)}/{len(results)}"
              f" | device {run['device']} | cold start {cold['total_s']:.1f}s (load {cold['load_s']:.1f}s,"
              f" warm-up {cold['warmup_ms']:.0f} ms) | footprint {run['footprint'] / 1e9:.2f} GB"
              f" (peak {run['peak_footprint'] / 1e9:.2f}) | rss {run['rss'] / 1e9:.2f} GB")
        for name, err in bad:
            print(f"   FAIL {name}: {err}")
        failures += bool(bad)
        client.post(f"/api/engines/{engine_id}/stop")
    print(f"\n{len(wanted) - failures}/{len(wanted)} engines passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
