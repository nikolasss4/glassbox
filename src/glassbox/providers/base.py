"""Provider interface: anything that can turn an observation into the next action."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from glassbox.actions import Action
from glassbox.browser import Observation
from glassbox.usage import Usage


class Decision(BaseModel):
    action: Action
    thought: str = ""
    usage: Usage = Field(default_factory=Usage)
    model: str = ""
    latency_s: float = 0.0
    # Provider-specific request/response details kept for the trace (never sent back).
    raw: dict[str, Any] | None = None


class Provider(ABC):
    """Stateful per run: `start()` once, then `decide()` once per step."""

    name: str

    @abstractmethod
    def start(self, goal: str, task_id: str | None = None) -> None: ...

    @abstractmethod
    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        """Return the next action. `feedback` describes the previous action's outcome."""
