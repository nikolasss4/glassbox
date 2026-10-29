"""The suite itself is tested: oracle solutions pass and a do-nothing agent fails."""

from pathlib import Path

from glassbox.actions import Action
from glassbox.browser import Observation
from glassbox.evals.report import markdown, per_task_markdown
from glassbox.evals.runner import OracleProvider, SuiteReport, _pct, run_suite
from glassbox.evals.tasks import TASKS, money, norm
from glassbox.providers.base import Decision, Provider


class GiveUpImmediately(Provider):
    """Claims success without doing anything. No check should accept that."""

    name = "noop"

    def start(self, goal: str, task_id: str | None = None) -> None:
        pass

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        return Decision(action=Action(name="done", args={"success": True, "answer": ""}))


async def test_oracle_solves_every_task(tmp_path: Path) -> None:
    report = await run_suite(OracleProvider, TASKS, runs_dir=tmp_path, concurrency=6)
    failed = [o.task_id for o in report.outcomes if not o.success]
    assert failed == []
    assert len(TASKS) >= 25


async def test_doing_nothing_passes_no_task(tmp_path: Path) -> None:
    report = await run_suite(GiveUpImmediately, TASKS, runs_dir=tmp_path, concurrency=6)
    passed = [o.task_id for o in report.outcomes if o.success]
    assert passed == []
    md = markdown([report])
    assert "| noop | 0% |" in md
    assert per_task_markdown([report]).count("❌") == len(TASKS)
    assert SuiteReport.from_json(report.to_json()).summary() == report.summary()
    assert report.diff(report) == []
    flipped = SuiteReport.from_json(report.to_json())
    flipped.outcomes[0].success = True
    assert report.diff(flipped) == [f"{flipped.outcomes[0].task_id}: expected pass, got fail"]


def test_helpers() -> None:
    assert norm('  "The Web,  Explained." ') == "the web, explained"
    assert money("It costs $1,075.60 total") == 1075.60
    assert _pct([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert _pct([], 95) == 0.0
