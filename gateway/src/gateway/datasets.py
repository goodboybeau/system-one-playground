"""Benchmark slices (datasets/*.jsonl) and playground presets (presets/*.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labkit import parse_request
from pydantic import ValidationError

from . import config


@dataclass(frozen=True)
class Item:
    id: str
    state: Any
    question: dict[str, Any]
    gold: Any
    lang: str | None = None

    def request(self) -> dict[str, Any]:
        return {"state": self.state, "questions": {"q": self.question}}


class DatasetError(ValueError):
    pass


def list_datasets(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or config.DATASETS_DIR
    index = {}
    if (root / "index.json").exists():
        index = json.loads((root / "index.json").read_text())
    out = []
    for path in sorted(root.glob("*.jsonl")):
        name = path.stem
        meta = index.get(name)
        if meta is None:
            first = json.loads(path.open().readline() or "{}")
            meta = {"title": name, "task": first.get("question", {}).get("type", "?"), "source": "custom",
                    "description": "Custom dataset", "items": sum(1 for line in path.open() if line.strip())}
        out.append({"name": name, **meta})
    return out


def load_items(name: str, limit: int | None = None, root: Path | None = None) -> list[Item]:
    root = root or config.DATASETS_DIR
    if not name.replace("_", "").replace("-", "").isalnum():
        raise DatasetError(f"invalid dataset name {name!r}")
    path = root / f"{name}.jsonl"
    if not path.exists():
        raise DatasetError(f"no dataset named {name!r}")
    items: list[Item] = []
    for n, line in enumerate(path.open(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            item = Item(id=str(raw["id"]), state=raw["state"], question=raw["question"], gold=raw["gold"], lang=raw.get("lang"))
            parse_request(item.request())
        except (ValueError, KeyError, ValidationError) as e:
            raise DatasetError(f"{path.name} line {n}: {e}") from e
        items.append(item)
        if limit and len(items) >= limit:
            break
    return items


def list_presets(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or config.PRESETS_DIR
    out = []
    for path in sorted(root.glob("*.json")):
        preset = json.loads(path.read_text())
        parse_request(preset["request"])
        out.append({"id": path.stem, **preset})
    return out
