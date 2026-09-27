"""Paths, the engine registry (engines.toml), and the lab's .env."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(os.environ.get("LAB_ROOT", Path(__file__).resolve().parents[3]))
RUN_DIR = Path(os.environ.get("LAB_RUN_DIR", ROOT / ".run"))
LOG_DIR = RUN_DIR / "logs"
DB_PATH = RUN_DIR / "lab.db"
DATASETS_DIR = ROOT / "datasets"
PRESETS_DIR = ROOT / "presets"
UI_DIST = ROOT / "ui" / "dist"
HOME_CACHE = Path.home() / ".cache"
HF_CACHE = Path(os.environ.get("HF_HUB_CACHE", Path.home() / ".cache" / "huggingface" / "hub"))


@dataclass(frozen=True)
class EngineSpec:
    id: str
    label: str
    project: Path
    loader: str
    model: str
    devices: tuple[str, ...]
    params: int
    architecture: str
    license: str
    source: str
    weights: tuple[str, ...]
    note: str
    remote: bool = False
    secrets: tuple[str, ...] = field(default_factory=tuple)

    @property
    def python(self) -> Path:
        return self.project / ".venv" / "bin" / "python"

    @property
    def installed(self) -> bool:
        return self.python.exists()

    def memory_estimate(self, device: str) -> int:
        """Rough bytes the weights need resident: fp32 on CPU and for encoders, 16-bit on the GPU."""
        if self.remote or not self.params:
            return 150_000_000
        encoder = self.architecture.startswith("encoder")
        bytes_per_param = 4 if device == "cpu" or encoder else 2
        return int(self.params * bytes_per_param * 1.15) + 400_000_000


def load_registry(path: Path | None = None) -> dict[str, EngineSpec]:
    path = path or ROOT / "engines.toml"
    with path.open("rb") as f:
        raw = tomllib.load(f)
    specs: dict[str, EngineSpec] = {}
    for e in raw.get("engine", []):
        spec = EngineSpec(
            id=e["id"], label=e["label"], project=(path.parent / e["project"]).resolve(), loader=e["loader"],
            model=e["model"], devices=tuple(e["devices"]), params=int(e["params"]),
            architecture=e["architecture"], license=e["license"], source=e["source"],
            weights=tuple(e.get("weights", [])), note=e.get("note", ""), remote=bool(e.get("remote", False)),
            secrets=tuple(e.get("secrets", [])),
        )
        if spec.id in specs:
            raise ValueError(f"duplicate engine id {spec.id!r} in {path}")
        if not spec.devices:
            raise ValueError(f"engine {spec.id!r} lists no devices")
        specs[spec.id] = spec
    return specs


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """KEY=value lines from the lab's .env; the process environment wins."""
    path = path or ROOT / ".env"
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip().removeprefix("export ").strip()] = value.strip().strip("'\"")
    return {**values, **{k: v for k, v in os.environ.items() if k in values}}


def missing_weights(repos: tuple[str, ...]) -> list[str]:
    """Repos (from "repo" or "repo:sub" entries) with no downloaded snapshot."""
    out = []
    for spec in repos:
        repo = spec.partition(":")[0]
        snaps = HF_CACHE / f"models--{repo.replace('/', '--')}" / "snapshots"
        if not (snaps.exists() and any(snaps.iterdir())) and repo not in out:
            out.append(repo)
    return out


def weights_on_disk(repos: tuple[str, ...]) -> int | None:
    """Bytes of the downloaded snapshots, following the hub's symlinks to shared blobs.

    An entry may name part of a repo: "repo:sub" counts only that subfolder, "repo:." only top-level files.
    """
    total, seen = 0, set()
    for spec in repos:
        repo, _, sub = spec.partition(":")
        snaps = HF_CACHE / f"models--{repo.replace('/', '--')}" / "snapshots"
        if not snaps.exists():
            return None
        for f in snaps.rglob("*"):
            rel = f.relative_to(snaps).parts[1:]
            if sub == "." and len(rel) > 1 or sub not in ("", ".") and (not rel or rel[0] != sub):
                continue
            if f.is_file():
                real = f.resolve()
                if real not in seen:
                    seen.add(real)
                    total += real.stat().st_size
    return total
