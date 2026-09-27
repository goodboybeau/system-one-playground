"""SQLite persistence: cold starts, peak memory per engine, and finished runs."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS cold_starts (
    id INTEGER PRIMARY KEY, engine TEXT NOT NULL, device TEXT NOT NULL, t REAL NOT NULL,
    process_s REAL, load_s REAL, warmup_ms REAL, total_s REAL, footprint INTEGER
);
CREATE TABLE IF NOT EXISTS peaks (
    engine TEXT NOT NULL, device TEXT NOT NULL, footprint INTEGER NOT NULL, t REAL NOT NULL,
    PRIMARY KEY (engine, device)
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, created REAL NOT NULL,
    finished REAL, status TEXT NOT NULL, config TEXT NOT NULL, result TEXT
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def record_cold_start(self, engine: str, device: str, cold: dict[str, Any], footprint: int | None) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO cold_starts (engine, device, t, process_s, load_s, warmup_ms, total_s, footprint) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (engine, device, time.time(), cold.get("process_s"), cold.get("load_s"), cold.get("warmup_ms"),
                 cold.get("total_s"), footprint))

    def cold_starts(self, engine: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        q = "SELECT * FROM cold_starts" + (" WHERE engine = ?" if engine else "") + " ORDER BY t DESC LIMIT ?"
        with self.lock:
            rows = self.db.execute(q, (engine, limit) if engine else (limit,)).fetchall()
        return [dict(r) for r in rows]

    def record_peak(self, engine: str, device: str, footprint: int) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO peaks (engine, device, footprint, t) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (engine, device) DO UPDATE SET footprint = MAX(footprint, excluded.footprint), t = excluded.t",
                (engine, device, footprint, time.time()))

    def peak_footprint(self, engine: str, device: str) -> int | None:
        with self.lock:
            row = self.db.execute("SELECT footprint FROM peaks WHERE engine = ? AND device = ?", (engine, device)).fetchone()
        return int(row["footprint"]) if row else None

    def peaks(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM peaks").fetchall()]

    def save_run(self, run_id: str, kind: str, title: str, created: float, status: str,
                 config: dict[str, Any], result: dict[str, Any] | None, finished: float | None) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO runs (id, kind, title, created, finished, status, config, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (id) DO UPDATE SET finished = excluded.finished, status = excluded.status, result = excluded.result",
                (run_id, kind, title, created, finished, status, json.dumps(config), json.dumps(result) if result is not None else None))

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id, kind, title, created, finished, status, config FROM runs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "config": json.loads(r["config"])} for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.lock:
            r = self.db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if r is None:
            return None
        return {**dict(r), "config": json.loads(r["config"]), "result": json.loads(r["result"]) if r["result"] else None}

    def delete_run(self, run_id: str) -> bool:
        with self.lock, self.db:
            return self.db.execute("DELETE FROM runs WHERE id = ?", (run_id,)).rowcount > 0
