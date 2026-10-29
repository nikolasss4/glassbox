"""Random-action baseline: the floor every real model should clear by a wide margin."""

from __future__ import annotations

import random
import re
import zlib

from glassbox.actions import Action
from glassbox.browser import Observation
from glassbox.providers.base import Decision, Provider

_REF = re.compile(r"^\[(e\d+)\] (\S+) ", re.M)
_TEXTY = {"textbox", "search", "email", "tel", "password", "number", "date"}
_WORDS = ["alice", "test", "hello", "2026", "lamp", "yes"]


class RandomProvider(Provider):
    """Clicks, types and scrolls at random, seeded per task so runs are reproducible."""

    name = "random"

    def __init__(self, max_actions: int = 12, seed: int = 0) -> None:
        self.max_actions = max_actions
        self.seed = seed
        self._rng = random.Random(seed)
        self._n = 0

    def start(self, goal: str, task_id: str | None = None) -> None:
        self._rng = random.Random(zlib.crc32(f"{self.seed}:{task_id or goal}".encode()))
        self._n = 0

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        self._n += 1
        elements = _REF.findall(obs.text)
        roll = self._rng.random()
        if self._n > self.max_actions or not elements:
            action = Action(name="done", args={"success": True, "answer": ""})
        elif roll < 0.15:
            action = Action(name="scroll", args={"direction": self._rng.choice(["up", "down"])})
        else:
            ref, role = self._rng.choice(elements)
            if role in _TEXTY:
                text = self._rng.choice(_WORDS)
                action = Action(name="type", args={"ref": ref, "text": text, "submit": False})
            else:
                action = Action(name="click", args={"ref": ref})
        action.reason = "random"
        return Decision(action=action, model=self.name)
