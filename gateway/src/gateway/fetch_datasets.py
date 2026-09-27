"""Build the benchmark slices in datasets/ from public Hugging Face datasets.

    uv run --project gateway python -m gateway.fetch_datasets

Each slice is a fixed, seeded sample written as JSONL, one item per line:
    {"id": str, "state": str | object, "question": {type, instructions, criteria}, "gold": label | level | bool}
Every item is checked against the /v1/systemone contract before it is written.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from typing import Any, Callable, Iterable

import httpx
from labkit import parse_request

from .config import DATASETS_DIR, RUN_DIR

API = "https://datasets-server.huggingface.co/rows"
SEED = 7
SIZE = 200
PAGE = 100
CACHE_DIR = RUN_DIR / "dataset-cache"

client = httpx.Client(timeout=60)


def _get(params: dict[str, Any]) -> dict[str, Any]:
    """One datasets-server page, cached on disk so reruns never refetch (the server rate-limits hard)."""
    key = "-".join(str(params[k]) for k in ("dataset", "config", "split", "offset", "length")).replace("/", "_")
    cached = CACHE_DIR / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    for attempt in range(10):
        try:
            r = client.get(API, params=params)
        except httpx.TransportError:
            time.sleep(min(90, 5 * 2**attempt))
            continue
        if r.status_code == 200:
            break
        if r.status_code != 429 and r.status_code < 500:
            r.raise_for_status()
        time.sleep(min(90, 5 * 2**attempt))
    else:
        raise RuntimeError(f"datasets-server kept failing for {params}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(r.text)
    return r.json()


def rows(dataset: str, config: str, split: str, pages: int, seed: int = SEED) -> list[dict[str, Any]]:
    """`pages` pages of 100 rows from seeded random offsets of the split."""
    base = {"dataset": dataset, "config": config, "split": split}
    total = _get({**base, "offset": 0, "length": 1})["num_rows_total"]
    rng = random.Random(f"{seed}-{dataset}-{config}")
    starts = sorted({rng.randrange(0, max(1, total - PAGE)) // PAGE * PAGE for _ in range(pages * 3)})[:pages]
    out: list[dict[str, Any]] = []
    for start in starts:
        out.extend(x["row"] for x in _get({**base, "offset": start, "length": PAGE})["rows"])
    return out


def all_rows(dataset: str, config: str, split: str) -> list[dict[str, Any]]:
    base = {"dataset": dataset, "config": config, "split": split}
    total = _get({**base, "offset": 0, "length": 1})["num_rows_total"]
    out: list[dict[str, Any]] = []
    for start in range(0, total, PAGE):
        out.extend(x["row"] for x in _get({**base, "offset": start, "length": PAGE})["rows"])
    return out


def sample(items: list[dict[str, Any]], n: int = SIZE, key: Callable[[dict], Any] | None = None) -> list[dict[str, Any]]:
    """Seeded sample of n, balanced across `key` values when given."""
    rng = random.Random(SEED)
    items = list(items)
    rng.shuffle(items)
    if key is None:
        return items[:n]
    groups: dict[Any, list[dict]] = {}
    for it in items:
        groups.setdefault(key(it), []).append(it)
    out: list[dict[str, Any]] = []
    while len(out) < n and any(groups.values()):
        for k in sorted(groups, key=str):
            if groups[k] and len(out) < n:
                out.append(groups[k].pop())
    rng.shuffle(out)
    return out


AG_NEWS = {"World": "international news, politics, conflicts, governments",
           "Sports": "sports, games, athletes, teams",
           "Business": "business, markets, companies, the economy",
           "Sci/Tech": "science, technology, computing, the internet"}
EMOTIONS = ["sadness", "joy", "love", "anger", "fear", "surprise"]
SST5 = ["very negative", "negative", "neutral", "positive", "very positive"]
MASSIVE = {"alarm": "setting or checking alarms", "audio": "volume and sound settings", "calendar": "events, meetings, reminders",
           "cooking": "recipes and cooking", "datetime": "dates and times", "email": "reading or sending email",
           "general": "chit-chat, jokes, general questions", "iot": "smart home devices, lights, plugs",
           "lists": "shopping and to-do lists", "music": "music preferences and info", "news": "news headlines",
           "play": "playing music, radio, podcasts, games", "qa": "factual questions, definitions, maths",
           "recommendation": "recommendations for places, events, movies", "social": "social media posts and complaints",
           "takeaway": "ordering food delivery", "transport": "trains, taxis, traffic, tickets", "weather": "weather forecasts"}
MASSIVE_LANGS = ["de", "fr", "pt", "ja", "hi", "sw"]


def build_ag_news() -> tuple[dict, list[dict]]:
    names = list(AG_NEWS)
    items = sample(rows("fancyzhx/ag_news", "default", "test", 6), key=lambda r: r["label"])
    q = {"type": "choice", "instructions": "What is this news article about?", "criteria": AG_NEWS}
    return ({"title": "AG News topics", "task": "choice", "labels": names, "source": "fancyzhx/ag_news (test)",
             "description": "4-way news topic classification. Easy; most models should clear 80%."},
            [{"id": f"ag-{i}", "state": r["text"], "question": q, "gold": names[int(r["label"])]} for i, r in enumerate(items)])


def build_emotion() -> tuple[dict, list[dict]]:
    items = sample(rows("dair-ai/emotion", "split", "test", 6), key=lambda r: r["label"])
    q = {"type": "choice", "instructions": "Which emotion does the writer express?", "criteria": EMOTIONS}
    return ({"title": "Emotion", "task": "choice", "labels": EMOTIONS, "source": "dair-ai/emotion (test)",
             "description": "6-way emotion of short English posts. Labels overlap (joy vs love), so expect confusion."},
            [{"id": f"emo-{i}", "state": r["text"], "question": q, "gold": EMOTIONS[int(r["label"])]} for i, r in enumerate(items)])


def _banking(n_labels: int | None) -> tuple[list[str], list[dict]]:
    everything = all_rows("mteb/banking77", "default", "test")
    counts = Counter(r["label_text"] for r in everything)
    labels = sorted(counts) if n_labels is None else sorted(label for label, _ in counts.most_common(n_labels))
    pool = [r for r in everything if r["label_text"] in labels]
    return labels, sample(pool, key=lambda r: r["label_text"])


def build_banking10() -> tuple[dict, list[dict]]:
    labels, items = _banking(10)
    q = {"type": "choice", "instructions": "What does the bank customer want?",
         "criteria": {label: label.replace("_", " ") for label in labels}}
    return ({"title": "Banking intents · 10", "task": "choice", "labels": labels, "source": "mteb/banking77 (test)",
             "description": "10 of the 77 Banking77 intents: fine-grained but a manageable option count."},
            [{"id": f"b10-{i}", "state": r["text"], "question": q, "gold": r["label_text"]} for i, r in enumerate(items)])


def build_banking77() -> tuple[dict, list[dict]]:
    labels, items = _banking(None)
    q = {"type": "choice", "instructions": "What does the bank customer want?", "criteria": labels}
    return ({"title": "Banking intents · 77 (stress)", "task": "choice", "labels": labels, "source": "mteb/banking77 (test)",
             "description": f"All {len(labels)} intents in one question. Stresses option budgets: some engines refuse it."},
            [{"id": f"b77-{i}", "state": r["text"], "question": q, "gold": r["label_text"]} for i, r in enumerate(items)])


def build_sst5() -> tuple[dict, list[dict]]:
    items = sample(rows("SetFit/sst5", "default", "test", 6), key=lambda r: r["label"])
    q = {"type": "score", "instructions": "How positive is this movie review?", "criteria": SST5}
    return ({"title": "SST-5 sentiment", "task": "score", "labels": [str(i) for i in range(5)], "legend": SST5,
             "source": "SetFit/sst5 (test)", "description": "5-level sentiment. Neighbouring levels are hard to tell apart; MAE matters more than accuracy."},
            [{"id": f"sst-{i}", "state": r["text"], "question": q, "gold": int(r["label"])} for i, r in enumerate(items)])


def build_spam() -> tuple[dict, list[dict]]:
    items = sample(rows("ucirvine/sms_spam", "plain_text", "train", 10), key=lambda r: r["label"])
    q = {"type": "noul", "instructions": "Is this text message spam?"}
    return ({"title": "SMS spam", "task": "noul", "source": "ucirvine/sms_spam",
             "description": "Balanced spam / not spam. A guardrail-style yes/no."},
            [{"id": f"spam-{i}", "state": r["sms"], "question": q, "gold": int(r["label"]) == 1} for i, r in enumerate(items)])


def build_injection() -> tuple[dict, list[dict]]:
    items = sample(rows("deepset/prompt-injections", "default", "train", 5), key=lambda r: r["label"])
    q = {"type": "noul", "instructions": "Is this message trying to override the assistant's instructions (a prompt injection or jailbreak)?"}
    return ({"title": "Prompt injections", "task": "noul", "source": "deepset/prompt-injections",
             "description": "Guardrail: spot injection attempts. Includes German examples."},
            [{"id": f"inj-{i}", "state": r["text"], "question": q, "gold": int(r["label"]) == 1} for i, r in enumerate(items)])


def build_pubmedqa() -> tuple[dict, list[dict]]:
    pool = [r for r in rows("qiaojin/PubMedQA", "pqa_labeled", "train", 10) if r["final_decision"] in ("yes", "no")]
    items = sample(pool, key=lambda r: r["final_decision"])
    q = {"type": "noul", "instructions": "Based on the abstract, is the answer to the research question yes?"}

    def state(r: dict) -> dict:
        ctx = r["context"]["contexts"] if isinstance(r["context"], dict) else []
        return {"question": r["question"], "abstract": "\n".join(ctx)}

    return ({"title": "PubMedQA", "task": "noul", "source": "qiaojin/PubMedQA (pqa_labeled)",
             "description": "Yes/no questions over full abstracts (~300-500 tokens): exposes short context windows."},
            [{"id": f"pmq-{i}", "state": state(r), "question": q, "gold": r["final_decision"] == "yes"} for i, r in enumerate(items)])


def build_massive() -> tuple[dict, list[dict]]:
    per_lang = SIZE // len(MASSIVE_LANGS) + 1
    q = {"type": "choice", "instructions": "What does the user want the voice assistant to do?", "criteria": MASSIVE}
    out: list[dict] = []
    for lang in MASSIVE_LANGS:
        pool = [r for r in rows("mteb/amazon_massive_scenario", lang, "test", 4) if r["label"] in MASSIVE]
        for r in sample(pool, per_lang, key=lambda r: r["label"]):
            out.append({"id": f"mas-{lang}-{len(out)}", "state": r["text"], "question": q, "gold": r["label"], "lang": lang})
    out = sample(out, SIZE, key=lambda r: r["lang"])
    return ({"title": "MASSIVE · 6 languages", "task": "choice", "labels": list(MASSIVE), "source": "mteb/amazon_massive_scenario",
             "description": "18-way voice-assistant scenarios in German, French, Portuguese, Japanese, Hindi and Swahili."}, out)


BUILDERS: dict[str, Callable[[], tuple[dict, list[dict]]]] = {
    "ag_news": build_ag_news, "emotion": build_emotion, "banking10": build_banking10, "banking77": build_banking77,
    "sst5": build_sst5, "sms_spam": build_spam, "prompt_injections": build_injection, "pubmedqa": build_pubmedqa,
    "massive": build_massive,
}


def check(items: Iterable[dict]) -> None:
    for it in items:
        parse_request({"state": it["state"], "questions": {"q": it["question"]}})


def main(argv: list[str] | None = None) -> None:
    import argparse
    import sys

    p = argparse.ArgumentParser(prog="gateway.fetch_datasets")
    p.add_argument("--force", action="store_true", help="rebuild slices that already exist")
    p.add_argument("names", nargs="*", help=f"slices to build (default: all of {', '.join(BUILDERS)})")
    args = p.parse_args(argv)
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    index_path = DATASETS_DIR / "index.json"
    index: dict[str, Any] = json.loads(index_path.read_text()) if index_path.exists() else {}
    failed = []
    for name in args.names or list(BUILDERS):
        if name not in BUILDERS:
            raise SystemExit(f"unknown dataset {name!r}; choose from {', '.join(BUILDERS)}")
        path = DATASETS_DIR / f"{name}.jsonl"
        if path.exists() and name in index and not args.force:
            print(f"{name:18} present")
            continue
        try:
            meta, items = BUILDERS[name]()
            check(items)
        except Exception as e:  # noqa: BLE001 - one flaky source must not stop the rest
            failed.append(name)
            print(f"{name:18} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        with path.open("w") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        index[name] = {**meta, "items": len(items), "seed": SEED}
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
        print(f"{name:18} {len(items):4} items  {meta['title']}")
    if failed:
        print(f"\n{len(failed)} slice(s) could not be fetched ({', '.join(failed)}); the rest work. Retry with `make datasets`.")


if __name__ == "__main__":
    main()
