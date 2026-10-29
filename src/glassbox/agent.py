"""The agent loop: observe -> decide -> act, with step budgets, timeouts and human takeover."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from glassbox.actions import Action, ActionResult
from glassbox.browser import BrowserSession, Observation
from glassbox.providers.base import Decision, Provider
from glassbox.usage import Usage

StopReason = Literal["done", "max_steps", "timeout", "error", "cancelled"]


class Step(BaseModel):
    index: int
    url: str
    observation_digest: str
    feedback: str | None = None  # what the model was told about the previous action
    thought: str
    action: Action
    result: ActionResult
    usage: Usage
    model: str
    latency_s: float
    action_s: float
    human_note: str | None = None
    # Not serialized into the step itself; the trace store writes it to a file.
    screenshot: bytes | None = Field(default=None, exclude=True)
    raw: dict[str, Any] | None = None


class RunResult(BaseModel):
    stop_reason: StopReason
    success_claimed: bool = False
    answer: str = ""
    steps: int = 0
    usage: Usage = Field(default_factory=Usage)
    cost_usd: float = 0.0
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class AgentConfig:
    max_steps: int = 25
    step_timeout_s: float = 90.0
    run_timeout_s: float = 600.0
    vision: bool = False
    screenshot_each_step: bool = True


class RunControl:
    """Shared between the loop and the UI: pause for takeover, resume with a note, cancel."""

    def __init__(self) -> None:
        self._running = asyncio.Event()
        self._running.set()
        self.cancelled = False
        self.takeovers = 0  # bumps on every pause, so the loop can spot one that came and went
        self._pending_note: str | None = None

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    def pause(self) -> None:
        if not self.paused:
            self.takeovers += 1
        self._running.clear()

    def resume(self, note: str | None = None) -> None:
        self._pending_note = (note or "").strip() or "no details given"
        self._running.set()

    def cancel(self) -> None:
        self.cancelled = True
        self._running.set()

    async def wait_if_paused(self) -> bool:
        """Block while paused. Returns True if a human took over during the wait."""
        if not self.paused:
            return False
        await self._running.wait()
        return True

    def take_note(self) -> str | None:
        note, self._pending_note = self._pending_note, None
        return note


EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _no_events(kind: str, data: dict[str, Any]) -> None:
    return None


@dataclass
class Agent:
    provider: Provider
    browser: BrowserSession
    config: AgentConfig = field(default_factory=AgentConfig)
    control: RunControl = field(default_factory=RunControl)
    on_event: EventSink = _no_events
    steps: list[Step] = field(default_factory=list)

    async def run(
        self, goal: str, start_url: str | None = None, task_id: str | None = None
    ) -> RunResult:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._loop(goal, start_url, task_id), timeout=self.config.run_timeout_s
            )
        except TimeoutError:
            result = RunResult(stop_reason="timeout", error="run timed out")
        except Exception as e:  # surfaced in the trace and the UI rather than crashing
            result = RunResult(stop_reason="error", error=f"{type(e).__name__}: {e}")
        result.steps = len(self.steps)
        result.usage = sum((s.usage for s in self.steps), Usage())
        result.cost_usd = sum(s.usage.cost(s.model) for s in self.steps)
        result.duration_s = round(time.monotonic() - started, 2)
        await self.on_event("run_finished", result.model_dump())
        return result

    async def _loop(self, goal: str, start_url: str | None, task_id: str | None) -> RunResult:
        if start_url:
            await self.browser.page.goto(start_url)
        self.provider.start(goal, task_id=task_id)
        await self.on_event("run_started", {"goal": goal, "start_url": start_url})

        feedback: str | None = None
        for index in range(self.config.max_steps):
            # A takeover between steps: the human's note reaches the model with the next look.
            if await self.control.wait_if_paused():
                feedback = _merge(feedback, self._human_feedback())
            if self.control.cancelled:
                return RunResult(stop_reason="cancelled")

            takeovers_before = self.control.takeovers
            obs = await self.browser.observe(screenshot=self.config.vision)
            try:
                decision = await asyncio.wait_for(
                    self.provider.decide(obs, feedback), timeout=self.config.step_timeout_s
                )
            except TimeoutError:
                return RunResult(stop_reason="timeout", error=f"step {index} timed out")

            human_note = None
            t0 = time.monotonic()
            if self.control.takeovers != takeovers_before or self.control.cancelled:
                # The human grabbed control while the model was thinking. Don't act on a
                # decision made for a page the human has since changed.
                await self.control.wait_if_paused()
                human_note = self.control.take_note()
                result = ActionResult(
                    ok=False,
                    message="Not executed: a human operator took control before this action ran. "
                    f"Their note: {human_note}. Look at the new snapshot before continuing.",
                )
            else:
                result = await self.browser.execute(decision.action)
            await self._record(
                index, obs, feedback, decision, result, time.monotonic() - t0, human_note
            )

            if self.control.cancelled:
                return RunResult(stop_reason="cancelled")
            if decision.action.name == "done" and human_note is None:
                return RunResult(
                    stop_reason="done",
                    success_claimed=bool(decision.action.args.get("success")),
                    answer=str(decision.action.args.get("answer", "")),
                )
            feedback = result.message if result.ok else f"FAILED: {result.message}"
        return RunResult(stop_reason="max_steps")

    def _human_feedback(self) -> str:
        note = self.control.take_note()
        return (
            "A human operator paused you and acted in the browser directly. "
            f"Their note: {note}. The page may have changed; continue from the new snapshot."
        )

    async def _record(
        self,
        index: int,
        obs: Observation,
        feedback: str | None,
        decision: Decision,
        result: ActionResult,
        action_s: float,
        human_note: str | None,
    ) -> Step:
        shot = await self.browser.screenshot() if self.config.screenshot_each_step else None
        step = Step(
            index=index,
            url=obs.url,
            observation_digest=obs.digest,
            feedback=feedback,
            thought=decision.thought,
            action=decision.action,
            result=result,
            usage=decision.usage,
            model=decision.model,
            latency_s=round(decision.latency_s, 3),
            action_s=round(action_s, 3),
            human_note=human_note,
            screenshot=shot,
            raw=decision.raw,
        )
        self.steps.append(step)
        await self.on_event("step", {"step": step, "observation": obs.text})
        return step


def _merge(a: str | None, b: str) -> str:
    return f"{a}\n{b}" if a else b
