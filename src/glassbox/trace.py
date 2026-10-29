"""File-based trace store: one directory per run with trace.json and per-step screenshots.

Layout:
    runs/<run_id>/trace.json      run metadata, every step (model I/O, action, result, usage)
    runs/<run_id>/step-000.jpg    screenshot taken after each step
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from glassbox.agent import Step

TRACE_VERSION = 1


def new_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


class TraceWriter:
    """Event sink for an Agent that keeps trace.json up to date as the run progresses."""

    def __init__(self, directory: Path, meta: dict[str, Any]) -> None:
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self._t0 = time.monotonic()
        self.doc: dict[str, Any] = {
            "version": TRACE_VERSION,
            "id": directory.name,
            "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "status": "running",
            **meta,
            "result": None,
            "steps": [],
            "events": [],
        }
        self._flush()

    @property
    def run_id(self) -> str:
        return str(self.doc["id"])

    async def on_event(self, kind: str, data: dict[str, Any]) -> None:
        if kind == "step":
            self.add_step(data["step"], data.get("observation", ""))
        elif kind == "run_finished":
            self.doc["status"] = "finished"
            self.doc["result"] = data
        else:
            self.add_event(kind, data)
        self._flush()

    def add_step(self, step: Step, observation: str) -> None:
        entry = step.model_dump(mode="json")
        entry["observation"] = observation
        entry["t"] = round(time.monotonic() - self._t0, 3)
        if step.screenshot:
            name = f"step-{step.index:03d}.jpg"
            (self.dir / name).write_bytes(step.screenshot)
            entry["screenshot"] = name
        self.doc["steps"].append(entry)

    def add_event(self, kind: str, data: dict[str, Any]) -> None:
        self.doc["events"].append(
            {"t": round(time.monotonic() - self._t0, 3), "kind": kind, **data}
        )
        self._flush()

    def _flush(self) -> None:
        tmp = self.dir / "trace.json.tmp"
        tmp.write_text(json.dumps(self.doc, indent=1, default=str))
        os.replace(tmp, self.dir / "trace.json")


class TraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create(self, meta: dict[str, Any], run_id: str | None = None) -> TraceWriter:
        return TraceWriter(self.root / (run_id or new_run_id()), meta)

    def load(self, run_id: str) -> dict[str, Any]:
        path = self._dir(run_id) / "trace.json"
        doc: dict[str, Any] = json.loads(path.read_text())
        return doc

    def asset(self, run_id: str, name: str) -> Path:
        path = (self._dir(run_id) / name).resolve()
        if path.parent != self._dir(run_id).resolve():
            raise FileNotFoundError(name)
        return path

    def list(self, limit: int = 200) -> list[dict[str, Any]]:
        """Newest first. Summaries only: no steps."""
        if not self.root.exists():
            return []
        out = []
        for d in sorted(self.root.iterdir(), reverse=True):
            f = d / "trace.json"
            if not f.is_file():
                continue
            try:
                doc = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            doc["n_steps"] = len(doc.pop("steps", []))
            doc.pop("events", None)
            out.append(doc)
            if len(out) >= limit:
                break
        return out

    def _dir(self, run_id: str) -> Path:
        if "/" in run_id or run_id.startswith("."):
            raise FileNotFoundError(run_id)
        d = self.root / run_id
        if not d.is_dir():
            raise FileNotFoundError(run_id)
        return d
