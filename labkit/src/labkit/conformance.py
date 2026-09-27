"""Check a running engine against the lab contract.

    python -m labkit.conformance http://127.0.0.1:9101

Exits non-zero if any check fails. Every engine must pass before the gateway lists it.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable

TRIAGE = {
    "state": {"subject": "Charged twice", "body": "I was billed twice for my March invoice. Please refund one charge."},
    "questions": {
        "team": {"type": "choice", "instructions": "Which team should handle this?",
                 "criteria": {"billing": "payments, invoices, refunds", "technical": "bugs, outages", "sales": "new purchases"}},
        "urgency": {"type": "score", "instructions": "How urgent is this?",
                    "criteria": ["not urgent", "somewhat urgent", "urgent", "critical"]},
        "refund": {"type": "noul", "instructions": "Is the customer asking for a refund?"},
    },
}


def _post(base: str, body: Any, raw: bytes | None = None) -> tuple[int, dict[str, Any]]:
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(base + "/v1/systemone", data=data, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(base: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read())


def _check_answers(req: dict[str, Any], body: dict[str, Any]) -> None:
    answers = body["answers"]
    assert set(answers) == set(req["questions"]), f"answer ids {sorted(answers)} != {sorted(req['questions'])}"
    for qid, q in req["questions"].items():
        a = answers[qid]
        assert a["type"] == q["type"], f"{qid}: type {a['type']} != {q['type']}"
        assert 0 <= a["confidence"] <= 1 and 0 <= a["p_top"] <= 1
        if q["type"] == "choice":
            labels = list(q["criteria"]) if isinstance(q["criteria"], dict) else q["criteria"]
            assert list(a["probabilities"]) == labels
            assert abs(sum(a["probabilities"].values()) - 1) < 1e-6
            assert a["choice"] in labels
        elif q["type"] == "score":
            n = len(q["criteria"])
            assert list(a["probabilities"]) == [str(i) for i in range(n)]
            assert 0 <= a["score"] <= n - 1 and 0 <= a["level"] < n
        else:
            assert 0 <= a["noul"] <= 1
    assert body["usage"]["output_tokens"] == 0
    assert body["timing"]["infer_ms"] >= 0


def run(base: str) -> list[tuple[str, str | None]]:
    base = base.rstrip("/")
    results: list[tuple[str, str | None]] = []

    def check(name: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            results.append((name, None))
        except AssertionError as e:
            results.append((name, str(e) or "assertion failed"))
        except Exception as e:  # noqa: BLE001
            results.append((name, f"{type(e).__name__}: {e}"))

    def ready() -> None:
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                h = _get(base, "/healthz")
            except urllib.error.URLError:
                time.sleep(0.5)
                continue
            assert h["status"] != "error", h["error"]
            if h["status"] == "ready":
                return
            time.sleep(0.5)
        raise AssertionError("engine not ready after 600 s")

    def info() -> None:
        i = _get(base, "/info")
        for key in ("engine", "model", "device", "load_seconds", "pid"):
            assert key in i, f"/info lacks {key}"

    def mixed() -> None:
        status, body = _post(base, TRIAGE)
        assert status == 200, body
        _check_answers(TRIAGE, body)

    def sensible() -> None:
        _, body = _post(base, TRIAGE)
        assert body["answers"]["team"]["choice"] == "billing", f"expected billing, got {body['answers']['team']}"

    def list_criteria_and_null_descriptions() -> None:
        req = {"state": "The app crashes every time I open settings.",
               "questions": {"kind": {"type": "choice", "instructions": "What kind of report is this?",
                                      "criteria": ["bug report", "feature request", "praise"]},
                             "area": {"type": "choice", "instructions": "Which area?",
                                      "criteria": {"settings": None, "billing": None}}}}
        status, body = _post(base, req)
        assert status == 200, body
        _check_answers(req, body)

    def string_and_array_state() -> None:
        for state in ("plain text state", [{"role": "user", "text": "hi"}, {"role": "agent", "text": "hello"}]):
            req = {"state": state, "questions": {"greet": {"type": "noul", "instructions": "Is this a greeting?"}}}
            status, body = _post(base, req)
            assert status == 200, body
            _check_answers(req, body)

    def unicode_state() -> None:
        req = {"state": "Mein Konto wurde zweimal belastet 💳 — 请退款",
               "questions": {"refund": {"type": "noul", "instructions": "Does the user want money back?"}}}
        status, body = _post(base, req)
        assert status == 200, body

    def noul_with_criteria() -> None:
        req = {"state": "Order #12 arrived broken.",
               "questions": {"damaged": {"type": "noul", "criteria": {"true": "item arrived damaged", "false": "item is fine"}}}}
        status, body = _post(base, req)
        assert status == 200, body
        _check_answers(req, body)

    def ten_level_score() -> None:
        req = {"state": "This is the best purchase I have ever made.",
               "questions": {"stars": {"type": "score", "instructions": "Rate the sentiment",
                                       "criteria": [f"{i} of 10" for i in range(1, 11)]}}}
        status, body = _post(base, req)
        assert status == 200, body
        _check_answers(req, body)

    def rejects_bad_json() -> None:
        status, body = _post(base, None, raw=b"{nope")
        assert status == 400 and "error" in body

    def rejects_invalid_question() -> None:
        status, body = _post(base, {"state": "x", "questions": {"q": {"type": "score", "criteria": ["one"]}}})
        assert status == 422 and "error" in body

    def deterministic() -> None:
        a = _post(base, TRIAGE)[1]["answers"]
        b = _post(base, TRIAGE)[1]["answers"]
        for qid in a:
            pa, pb = a[qid].get("probabilities"), b[qid].get("probabilities")
            if pa:
                assert all(abs(pa[k] - pb[k]) < 1e-3 for k in pa), f"{qid} drifted: {pa} vs {pb}"
            else:
                assert abs(a[qid]["noul"] - b[qid]["noul"]) < 1e-3

    for name, fn in [("ready", ready), ("info", info), ("mixed question types", mixed),
                     ("routes the billing ticket to billing", sensible),
                     ("list criteria and null descriptions", list_criteria_and_null_descriptions),
                     ("string and array state", string_and_array_state), ("unicode state", unicode_state),
                     ("noul with criteria only", noul_with_criteria), ("10-level score", ten_level_score),
                     ("rejects malformed JSON", rejects_bad_json), ("rejects invalid question", rejects_invalid_question),
                     ("deterministic", deterministic)]:
        check(name, fn)
        if name == "ready" and results[-1][1]:
            break
    return results


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m labkit.conformance <base-url>")
    results = run(sys.argv[1])
    for name, err in results:
        print(("PASS " if err is None else "FAIL ") + name + ("" if err is None else f"\n     {err}"))
    failed = sum(1 for _, e in results if e)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
