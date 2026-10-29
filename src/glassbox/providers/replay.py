"""Record-and-replay: capture a provider's decisions once, replay them offline.

A fixture stores each decision together with a digest of the snapshot the model saw.
Replay checks the digest before handing back the decision, so a change to the mock sites
or the snapshotter fails loudly instead of silently replaying actions onto a different page.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from glassbox.browser import Observation
from glassbox.providers.base import Decision, Provider


class FixtureDrift(RuntimeError):
    pass


def fixture_path(root: Path, task_id: str) -> Path:
    return root / f"{task_id}.json"


class RecordingProvider(Provider):
    def __init__(self, inner: Provider, root: Path) -> None:
        self.inner = inner
        self.root = root
        self.name = inner.name
        self._task_id = ""
        self._goal = ""
        self._entries: list[dict[str, object]] = []

    def start(self, goal: str, task_id: str | None = None) -> None:
        if not task_id:
            raise ValueError("recording needs a task id")
        self._task_id, self._goal, self._entries = task_id, goal, []
        self.inner.start(goal, task_id)

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        decision = await self.inner.decide(obs, feedback)
        self._entries.append(
            {"observation_digest": obs.digest, "decision": decision.model_dump(exclude={"raw"})}
        )
        self._save()
        return decision

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        doc = {
            "task_id": self._task_id,
            "goal": self._goal,
            "provider": self.inner.name,
            "recorded_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "decisions": self._entries,
        }
        fixture_path(self.root, self._task_id).write_text(json.dumps(doc, indent=1) + "\n")


class ReplayProvider(Provider):
    def __init__(self, root: Path, *, strict: bool = True) -> None:
        self.root = root
        self.strict = strict
        self.name = f"replay:{root.name}"
        self._queue: list[dict[str, object]] = []
        self._task_id = ""

    def start(self, goal: str, task_id: str | None = None) -> None:
        if not task_id:
            raise ValueError("replay needs a task id")
        self._task_id = task_id
        doc = json.loads(fixture_path(self.root, task_id).read_text())
        self.name = f"replay:{doc['provider']}"
        self._queue = list(doc["decisions"])

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        if not self._queue:
            raise FixtureDrift(f"{self._task_id}: fixture ran out of decisions")
        entry = self._queue.pop(0)
        if self.strict and entry["observation_digest"] != obs.digest:
            raise FixtureDrift(
                f"{self._task_id}: page snapshot differs from the recording "
                f"(expected {entry['observation_digest']}, got {obs.digest}). "
                "Re-record the fixture if the change is intended."
            )
        return Decision.model_validate(entry["decision"])
