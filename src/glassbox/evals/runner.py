"""Run a task suite against a provider and summarize the results."""

from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import json
import statistics
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from glassbox.agent import Agent, AgentConfig, RunResult
from glassbox.browser import VIEWPORT, BrowserSession, Observation
from glassbox.evals.tasks import TASKS_BY_ID, CheckContext, Task
from glassbox.providers import Provider, register
from glassbox.providers.base import Decision
from glassbox.providers.replay import RecordingProvider
from glassbox.providers.scripted import ScriptedProvider
from glassbox.sitesrv import SiteServer
from glassbox.trace import TraceStore

ProviderFactory = Callable[[], Provider]


class OracleProvider(Provider):
    """Plays each task's hand-written solution. Should always score 100%."""

    name = "oracle"

    def __init__(self) -> None:
        self._inner = ScriptedProvider([], name="oracle")

    def start(self, goal: str, task_id: str | None = None) -> None:
        if task_id not in TASKS_BY_ID:
            raise ValueError("the oracle only knows tasks from the eval suite")
        self._inner = ScriptedProvider(TASKS_BY_ID[task_id].oracle, name="oracle")

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        return await self._inner.decide(obs, feedback)


register("oracle", OracleProvider)


@dataclass
class TaskOutcome:
    task_id: str
    trial: int
    success: bool
    stop_reason: str
    steps: int
    cost_usd: float
    duration_s: float
    step_latencies: list[float]
    answer: str
    run_id: str
    tags: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class SuiteReport:
    provider: str
    suite: str
    created_at: str
    effort: str
    outcomes: list[TaskOutcome]

    def summary(self) -> dict[str, Any]:
        o = self.outcomes
        lat = sorted(x for t in o for x in t.step_latencies)
        n = max(len(o), 1)
        return {
            "provider": self.provider,
            "tasks": len({t.task_id for t in o}),
            "runs": len(o),
            "success_rate": sum(t.success for t in o) / n,
            "mean_steps": sum(t.steps for t in o) / n,
            "cost_per_task_usd": sum(t.cost_usd for t in o) / n,
            "total_cost_usd": sum(t.cost_usd for t in o),
            "p50_step_latency_s": _pct(lat, 50),
            "p95_step_latency_s": _pct(lat, 95),
            "p50_task_duration_s": statistics.median([t.duration_s for t in o]) if o else 0.0,
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "suite": self.suite,
            "created_at": self.created_at,
            "effort": self.effort,
            "summary": self.summary(),
            "outcomes": [asdict(t) for t in self.outcomes],
        }

    @classmethod
    def from_json(cls, doc: dict[str, Any]) -> SuiteReport:
        return cls(
            provider=doc["provider"],
            suite=doc["suite"],
            created_at=doc["created_at"],
            effort=doc.get("effort", ""),
            outcomes=[TaskOutcome(**t) for t in doc["outcomes"]],
        )


def _pct(sorted_values: list[float], p: int) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


async def read_store(page: Page) -> dict[str, Any]:
    raw: dict[str, str] = await page.evaluate(
        "() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('gb:'))"
        ".map(k => [k.slice(3), localStorage.getItem(k)]))"
    )
    return {k: json.loads(v) for k, v in raw.items()}


async def run_task(
    browser: Browser,
    base_url: str,
    task: Task,
    provider: Provider,
    *,
    store: TraceStore,
    trial: int = 0,
    vision: bool = False,
    on_step: Callable[[str], None] | None = None,
) -> TaskOutcome:
    context = await browser.new_context(viewport=VIEWPORT)
    page = await context.new_page()
    try:
        if task.setup:
            await page.goto(f"{base_url}/sites/")
            await page.evaluate(
                "(items) => { for (const [k, v] of Object.entries(items)) "
                "localStorage.setItem('gb:' + k, JSON.stringify(v)); }",
                task.setup,
            )
        writer = store.create(
            {
                "goal": task.goal,
                "start_url": task.start,
                "task_id": task.id,
                "provider": provider.name,
                "eval": {"trial": trial},
            }
        )

        async def on_event(kind: str, data: dict[str, Any]) -> None:
            await writer.on_event(kind, data)
            if kind == "step" and on_step:
                on_step(f"{task.id} #{data['step'].index} {data['step'].action.short()}")

        agent = Agent(
            provider=provider,
            browser=BrowserSession(page, allowed_origins=[base_url]),
            config=AgentConfig(max_steps=task.max_steps, vision=vision),
            on_event=on_event,
        )
        result = await agent.run(task.goal, f"{base_url}{task.start}", task_id=task.id)
        success, check_error = await _check(task, page, result)
        writer.add_event("check", {"success": success, "error": check_error})
        return TaskOutcome(
            task_id=task.id,
            trial=trial,
            success=success,
            stop_reason=result.stop_reason,
            steps=result.steps,
            cost_usd=round(result.cost_usd, 6),
            duration_s=result.duration_s,
            step_latencies=[s.latency_s for s in agent.steps],
            answer=result.answer,
            run_id=writer.run_id,
            tags=task.tags,
            error=result.error or check_error,
        )
    finally:
        await context.close()


async def _check(task: Task, page: Page, result: RunResult) -> tuple[bool, str | None]:
    try:
        ctx = CheckContext(page=page, result=result, store=await read_store(page))
        verdict = task.check(ctx)
        if inspect.isawaitable(verdict):
            verdict = await verdict
        return bool(verdict), None
    except Exception as e:
        return False, f"check failed: {type(e).__name__}: {e}"


async def run_suite(
    factory: ProviderFactory,
    tasks: list[Task],
    *,
    suite: str = "local",
    runs_dir: Path = Path("runs"),
    record_dir: Path | None = None,
    concurrency: int = 1,
    trials: int = 1,
    vision: bool = False,
    effort: str = "medium",
    headless: bool = True,
    on_step: Callable[[str], None] | None = None,
    on_outcome: Callable[[TaskOutcome], None] | None = None,
) -> SuiteReport:
    store = TraceStore(runs_dir)
    sem = asyncio.Semaphore(concurrency)
    name = factory().name

    with SiteServer() as sites:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)

            async def one(task: Task, trial: int) -> TaskOutcome:
                async with sem:
                    provider = factory()
                    if record_dir is not None:
                        provider = RecordingProvider(provider, record_dir)
                    outcome = await run_task(
                        browser, sites.base_url, task, provider,
                        store=store, trial=trial, vision=vision, on_step=on_step,
                    )  # fmt: skip
                    if on_outcome:
                        on_outcome(outcome)
                    return outcome

            jobs = [one(task, trial) for trial in range(trials) for task in tasks]
            outcomes = await asyncio.gather(*jobs)
            await browser.close()

    return SuiteReport(
        provider=name,
        suite=suite,
        created_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        effort=effort,
        outcomes=list(outcomes),
    )
