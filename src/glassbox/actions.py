"""The agent's action space: one schema shared by every provider, the executor and the trace."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ActionName = Literal[
    "navigate", "click", "type", "select_option", "press_key", "scroll", "wait", "extract", "done"
]


class Action(BaseModel):
    name: ActionName
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""

    def short(self) -> str:
        """Compact human-readable form for logs and the timeline, e.g. `click(e12)`."""
        shown = {k: v for k, v in self.args.items() if k != "reason"}
        inner = ", ".join(f"{k}={v!r}" if k != "ref" else str(v) for k, v in shown.items())
        return f"{self.name}({inner})"


class ActionResult(BaseModel):
    ok: bool
    message: str


_REASON = {
    "type": "string",
    "description": "One short sentence: why this action moves the task forward.",
}


def _tool(name: str, description: str, props: dict[str, Any]) -> dict[str, Any]:
    properties = {**props, "reason": _REASON}
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


_REF = {"type": "string", "description": "Element ref from the snapshot, e.g. e12."}

TOOLS: list[dict[str, Any]] = [
    _tool("navigate", "Open a URL in the current tab.", {"url": {"type": "string"}}),
    _tool("click", "Click an element by its snapshot ref.", {"ref": _REF}),
    _tool(
        "type",
        "Replace the contents of a text field with `text`. Set submit=true to press Enter after.",
        {"ref": _REF, "text": {"type": "string"}, "submit": {"type": "boolean"}},
    ),
    _tool(
        "select_option",
        "Choose an option of a native <select> element by its visible label.",
        {"ref": _REF, "option": {"type": "string"}},
    ),
    _tool(
        "press_key",
        "Press a keyboard key on the focused element, e.g. Enter, Escape, Tab, ArrowDown.",
        {"key": {"type": "string"}},
    ),
    _tool(
        "scroll",
        "Scroll the page by about one screen.",
        {"direction": {"type": "string", "enum": ["up", "down"]}},
    ),
    _tool(
        "wait",
        "Wait for the page to change, e.g. while a spinner is showing. 1 to 5 seconds.",
        {"seconds": {"type": "number"}},
    ),
    _tool(
        "extract",
        "Write down a fact you found on the page so you can use it later in the task.",
        {"data": {"type": "string"}},
    ),
    _tool(
        "done",
        "Finish the task. `answer` holds the requested information, or a summary of what you "
        "did. Set success=false if the task cannot be completed.",
        {"success": {"type": "boolean"}, "answer": {"type": "string"}},
    ),
]

TOOL_NAMES: set[str] = {t["name"] for t in TOOLS}


def action_from_tool_call(name: str, tool_input: dict[str, Any]) -> Action:
    args = dict(tool_input)
    reason = str(args.pop("reason", ""))
    return Action(name=name, args=args, reason=reason)  # type: ignore[arg-type]
