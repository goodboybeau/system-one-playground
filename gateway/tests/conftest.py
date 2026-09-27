"""Every gateway test runs against a throwaway lab root with mock engines that are real processes."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

LABKIT = Path(__file__).resolve().parents[2] / "labkit"
ROOT = Path(tempfile.mkdtemp(prefix="lab-test-"))
os.environ["LAB_ROOT"] = str(ROOT)

MOCKS = {
    "fast": "lexical", "slow": "slow:60", "failload": "fail-load", "exitload": "exit-load",
    "probe": "probe-network", "slowload": "slow:1",
}
toml = []
for engine_id, model in MOCKS.items():
    toml.append(f"""[[engine]]
id = "{engine_id}"
label = "Mock {engine_id}"
project = "{LABKIT}"
loader = "labkit.mock:load"
model = "{model}"
devices = ["cpu", "mps"]
params = 0
architecture = "mock"
license = "n/a"
source = "test"
weights = []
""")
toml.append(f"""[[engine]]
id = "huge"
label = "Mock huge"
project = "{LABKIT}"
loader = "labkit.mock:load"
model = "lexical"
devices = ["cpu"]
params = 900_000_000_000
architecture = "mock"
license = "n/a"
source = "test"
weights = []
""")
(ROOT / "engines.toml").write_text("\n".join(toml))

(ROOT / "datasets").mkdir()
Q = {"type": "choice", "instructions": "Which team?",
     "criteria": {"billing": "payment refund charged invoice", "technical": "crash bug error app"}}
rows = [
    {"id": "1", "state": "I was charged twice, refund the payment", "question": Q, "gold": "billing"},
    {"id": "2", "state": "the app crashes with an error", "question": Q, "gold": "technical"},
    {"id": "3", "state": "invoice payment is wrong", "question": Q, "gold": "billing"},
    {"id": "4", "state": "hello there", "question": Q, "gold": "technical"},
]
(ROOT / "datasets" / "tiny.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
(ROOT / "datasets" / "index.json").write_text(json.dumps(
    {"tiny": {"title": "Tiny", "task": "choice", "labels": ["billing", "technical"], "source": "test",
              "description": "four tickets", "items": 4}}))
(ROOT / "presets").mkdir()
(ROOT / "presets" / "triage.json").write_text(json.dumps(
    {"title": "Triage", "description": "d", "request": {"state": "charged twice", "questions": {"team": Q}}}))

BODY = {"state": "I was charged twice, please refund", "questions": {"team": Q}}


def wait_for(fn, timeout=30.0, interval=0.1):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"condition not met in {timeout}s; last={last!r}")


@pytest.fixture()
def lab():
    from fastapi.testclient import TestClient

    from gateway.app import create_app
    from gateway.store import Store

    store = Store(ROOT / ".run" / f"test-{time.time_ns()}.db")
    app = create_app(sandbox=True, store=store)
    with TestClient(app) as client:
        yield client
        for e in client.get("/api/engines").json():
            if e["run"]:
                client.post(f"/api/engines/{e['id']}/stop")


def start_ready(client, engine_id, **body):
    r = client.post(f"/api/engines/{engine_id}/start", json=body)
    assert r.status_code == 200, r.text
    return wait_for(lambda: (e := client.get(f"/api/engines/{engine_id}").json())["run"]
                    and e["run"]["status"] in ("ready", "error", "exited") and e)


@pytest.fixture(autouse=True)
def no_leaked_engines():
    import psutil

    yield

    def leaked():
        return [p.pid for p in psutil.Process().children(recursive=True)
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE and "labkit.serve" in " ".join(p.cmdline())]

    try:
        wait_for(lambda: not leaked(), timeout=8)
    except AssertionError:
        raise AssertionError(f"engine processes leaked: {leaked()}") from None
