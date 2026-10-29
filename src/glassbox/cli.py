"""Command line: `glassbox serve | run | eval | report | tasks | sites`."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from glassbox.config import DEFAULT_MODEL

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)
# Wide enough for the results table when output is piped (rich assumes 80 columns).
console = Console(width=None if sys.stdout.isatty() else 140)


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    runs_dir: Path = Path("runs"),
    headed: Annotated[bool, typer.Option(help="Show the Chromium window too.")] = False,
) -> None:
    """Start the API, live view and replay UI."""
    import uvicorn

    from glassbox.server import create_app

    uvicorn.run(create_app(runs_dir, headless=not headed), host=host, port=port)


@app.command()
def tasks() -> None:
    """List the tasks in the local suite."""
    from glassbox.evals.tasks import TASKS

    for t in TASKS:
        console.print(f"[bold]{t.id}[/] [dim]{','.join(t.tags)}[/]\n  {t.goal}")


@app.command()
def sites(port: int = 8100) -> None:
    """Serve only the mock sites (http://127.0.0.1:PORT/sites/)."""
    import uvicorn

    from glassbox.sitesrv import create_sites_app

    uvicorn.run(create_sites_app(), host="127.0.0.1", port=port)


@app.command()
def run(
    goal: str,
    url: Annotated[str, typer.Option(help="Start URL.")] = "about:blank",
    model: str = DEFAULT_MODEL,
    effort: str = "medium",
    max_steps: int = 25,
    vision: bool = False,
    headed: bool = False,
    runs_dir: Path = Path("runs"),
) -> None:
    """Run one task in the terminal and save its trace."""
    from playwright.async_api import async_playwright

    from glassbox.agent import Agent, AgentConfig
    from glassbox.browser import VIEWPORT, BrowserSession
    from glassbox.providers import get_provider
    from glassbox.trace import TraceStore

    async def main() -> None:
        provider = get_provider(model, effort=effort)
        writer = TraceStore(runs_dir).create(
            {"goal": goal, "start_url": url, "provider": provider.name}
        )

        async def on_event(kind: str, data: dict[str, Any]) -> None:
            await writer.on_event(kind, data)
            if kind == "step":
                s = data["step"]
                mark = "[green]✓[/]" if s.result.ok else "[red]✗[/]"
                console.print(
                    f"{mark} [bold]{s.index:>2}[/] {s.action.short()}  [dim]{s.thought}[/]"
                )
                if not s.result.ok:
                    console.print(f"     [red]{s.result.message}[/]")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=not headed)
            page = await (await browser.new_context(viewport=VIEWPORT)).new_page()
            agent = Agent(
                provider=provider,
                browser=BrowserSession(page),
                config=AgentConfig(max_steps=max_steps, vision=vision),
                on_event=on_event,
            )
            result = await agent.run(goal, url)
            await browser.close()
        console.print(
            f"\n[bold]{result.stop_reason}[/] · answer: {result.answer!r} · {result.steps} steps · "
            f"${result.cost_usd:.4f} · trace: {writer.dir}"
        )

    asyncio.run(main())


@app.command("eval")
def eval_(
    model: Annotated[
        list[str],
        typer.Option(
            help="Agent to evaluate; repeat to compare. A model name/alias, "
            "'random', 'oracle' or 'replay:<fixture dir>'."
        ),
    ] = [DEFAULT_MODEL],  # noqa: B006
    suite: str = "local",
    task: Annotated[list[str] | None, typer.Option(help="Only these task ids.")] = None,
    trials: int = 1,
    concurrency: int = 4,
    effort: str = "medium",
    vision: bool = False,
    record: Annotated[
        Path | None, typer.Option(help="Save decisions as replay fixtures under DIR/<agent>/.")
    ] = None,
    out: Path = Path("results"),
    runs_dir: Path = Path("runs"),
    min_success: Annotated[
        float | None, typer.Option(help="Exit 1 if any agent's success rate is below this.")
    ] = None,
    expect: Annotated[
        Path | None,
        typer.Option(help="Saved results JSON; exit 1 unless every task's pass/fail matches it."),
    ] = None,
) -> None:
    """Run the eval suite and print a results table."""
    from glassbox.evals.report import markdown, per_task_markdown, summary_table
    from glassbox.evals.runner import TaskOutcome, run_suite
    from glassbox.evals.tasks import SUITES, TASKS_BY_ID
    from glassbox.providers import get_provider

    if suite not in SUITES:
        raise typer.BadParameter(f"unknown suite {suite!r}; choose from {sorted(SUITES)}")
    selected = [TASKS_BY_ID[t] for t in task] if task else SUITES[suite]
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    for spec in model:
        name = get_provider(spec, effort=effort).name
        console.rule(f"[bold]{name}[/] · {len(selected)} tasks × {trials} trial(s)")

        def show(o: TaskOutcome) -> None:
            mark = "[green]PASS[/]" if o.success else "[red]FAIL[/]"
            extra = f" [dim]{o.error}[/]" if o.error else ""
            console.print(f"{mark} {o.task_id:<26} {o.steps:>2} steps ${o.cost_usd:.4f}{extra}")

        started = time.monotonic()
        report = asyncio.run(
            run_suite(
                lambda spec=spec: get_provider(spec, effort=effort),  # type: ignore[misc]
                selected,
                suite=suite,
                runs_dir=runs_dir,
                record_dir=record / name.replace("replay:", "") if record else None,
                concurrency=concurrency,
                trials=trials,
                vision=vision,
                effort=effort,
                on_outcome=show,
            )
        )
        console.print(f"[dim]{time.monotonic() - started:.0f}s wall clock[/]")
        path = out / f"{suite}__{name.replace(':', '_').replace('/', '_')}.json"
        path.write_text(json.dumps(report.to_json(), indent=1) + "\n")
        reports.append(report)

    console.print(summary_table(reports))
    (out / f"{suite}.md").write_text(markdown(reports) + "\n\n" + per_task_markdown(reports) + "\n")
    console.print(f"[dim]results written to {out}/[/]")
    if min_success is not None and any(r.summary()["success_rate"] < min_success for r in reports):
        raise typer.Exit(1)
    if expect is not None:
        from glassbox.evals.runner import SuiteReport

        want = SuiteReport.from_json(json.loads(expect.read_text()))
        diffs = [d for r in reports for d in r.diff(want)]
        for d in diffs:
            console.print(f"[red]mismatch[/] {d}")
        if diffs:
            raise typer.Exit(1)
        console.print(f"[green]outcomes match {expect}[/]")


@app.command()
def report(files: list[Path], per_task: bool = False) -> None:
    """Combine saved results JSON files into one Markdown table."""
    from glassbox.evals.report import markdown, per_task_markdown
    from glassbox.evals.runner import SuiteReport

    reports = [SuiteReport.from_json(json.loads(f.read_text())) for f in files]
    print(markdown(reports))
    if per_task:
        print()
        print(per_task_markdown(reports))


if __name__ == "__main__":
    app()
