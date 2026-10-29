"""Render suite reports as terminal tables and Markdown."""

from __future__ import annotations

from rich.table import Table

from glassbox.evals.runner import SuiteReport

_COLUMNS = [
    ("Agent", "provider", "{}"),
    ("Success", "success_rate", "{:.0%}"),
    ("Mean steps", "mean_steps", "{:.1f}"),
    ("Cost / task", "cost_per_task_usd", "${:.4f}"),
    ("p50 step latency", "p50_step_latency_s", "{:.2f}s"),
    ("p95 step latency", "p95_step_latency_s", "{:.2f}s"),
    ("p50 task time", "p50_task_duration_s", "{:.1f}s"),
]


def _cells(report: SuiteReport) -> list[str]:
    s = report.summary()
    label = s["provider"] + (f" ({report.effort})" if report.effort and _is_llm(report) else "")
    return [label] + [fmt.format(s[key]) for _, key, fmt in _COLUMNS[1:]]


def _is_llm(report: SuiteReport) -> bool:
    return report.provider.startswith("claude-") or report.provider.startswith("replay:claude")


def summary_table(reports: list[SuiteReport]) -> Table:
    table = Table(
        title=f"glassbox eval · suite={reports[0].suite} · {reports[0].summary()['tasks']} tasks"
    )
    for title, _, _ in _COLUMNS:
        table.add_column(title, justify="left" if title == "Agent" else "right")
    for r in reports:
        table.add_row(*_cells(r))
    return table


def markdown(reports: list[SuiteReport]) -> str:
    head = "| " + " | ".join(t for t, _, _ in _COLUMNS) + " |"
    sep = "|" + "|".join([":---"] + ["---:"] * (len(_COLUMNS) - 1)) + "|"
    rows = ["| " + " | ".join(_cells(r)) + " |" for r in reports]
    return "\n".join([head, sep, *rows])


def per_task_markdown(reports: list[SuiteReport]) -> str:
    """Task x agent matrix; a cell shows passes/trials."""
    tasks: list[str] = []
    for r in reports:
        for o in r.outcomes:
            if o.task_id not in tasks:
                tasks.append(o.task_id)
    head = "| Task | " + " | ".join(r.provider for r in reports) + " |"
    sep = "|:---|" + "|".join([":---:"] * len(reports)) + "|"
    rows = []
    for task in tasks:
        cells = []
        for r in reports:
            runs = [o for o in r.outcomes if o.task_id == task]
            ok = sum(o.success for o in runs)
            cells.append(
                "✅" if runs and ok == len(runs) else "❌" if ok == 0 else f"{ok}/{len(runs)}"
            )
        rows.append(f"| `{task}` | " + " | ".join(cells) + " |")
    return "\n".join([head, sep, *rows])
