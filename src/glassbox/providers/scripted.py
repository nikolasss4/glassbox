"""Scripted provider: plays a fixed list of steps, resolving element names to refs.

Used by tests and by the eval suite's oracle (a hand-written solution per task that proves
each task is solvable and each success check is correct).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from glassbox.actions import Action
from glassbox.browser import Observation
from glassbox.providers.base import Decision, Provider

_LINE = re.compile(r'^\[(e\d+)\] (\S+) "(.*?)"(.*)$')


@dataclass
class S:
    """One scripted step. `target` is matched against element names in the snapshot."""

    action: str
    target: str | None = None
    role: str | None = None
    nth: int = 0
    args: dict[str, Any] = field(default_factory=dict)


def find_ref(snapshot: str, target: str, role: str | None = None, nth: int = 0) -> str | None:
    """Find the ref of the nth element whose name contains `target` (case-insensitive)."""
    hits = []
    for line in snapshot.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        ref, line_role, name, _ = m.groups()
        if role and line_role != role:
            continue
        if target.lower() in name.lower():
            hits.append(ref)
    return hits[nth] if len(hits) > nth else None


class ScriptedProvider(Provider):
    def __init__(self, steps: list[S], name: str = "scripted") -> None:
        self.name = name
        self.script = steps
        self._i = 0

    def start(self, goal: str, task_id: str | None = None) -> None:
        self._i = 0

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        if self._i >= len(self.script):
            action = Action(name="done", args={"success": False, "answer": "script exhausted"})
            return Decision(action=action, model=self.name)
        step = self.script[self._i]
        self._i += 1
        args = dict(step.args)
        if step.target is not None:
            ref = find_ref(obs.text, step.target, step.role, step.nth)
            if ref is None:
                # Leave a ref that cannot exist so the failure shows up clearly in the trace.
                ref = "e0"
            args["ref"] = ref
        action = Action(name=step.action, args=args, reason=f"script step {self._i}")  # type: ignore[arg-type]
        return Decision(action=action, model=self.name)
