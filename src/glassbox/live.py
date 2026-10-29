"""CDP plumbing for the live view: screencast frames out, human input in."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from playwright.async_api import CDPSession, Page

FrameSink = Callable[[dict[str, Any]], Awaitable[None]]

# Keys that need a virtual key code for Chromium to act on them (not just insert text).
_KEY_CODES = {
    "Backspace": 8,
    "Tab": 9,
    "Enter": 13,
    "Escape": 27,
    "PageUp": 33,
    "PageDown": 34,
    "End": 35,
    "Home": 36,
    "ArrowLeft": 37,
    "ArrowUp": 38,
    "ArrowRight": 39,
    "ArrowDown": 40,
    "Delete": 46,
}
_MOUSE_TYPES = {"mousePressed", "mouseReleased", "mouseMoved", "mouseWheel"}


class Screencast:
    """Streams JPEG frames from `Page.startScreencast` to a sink, acking each frame."""

    def __init__(self, page: Page, sink: FrameSink, quality: int = 60) -> None:
        self.page = page
        self.sink = sink
        self.quality = quality
        self.cdp: CDPSession | None = None
        self.last_frame: dict[str, Any] | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        viewport = self.page.viewport_size or {"width": 1280, "height": 800}
        await self.cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": self.quality,
                "maxWidth": viewport["width"],
                "maxHeight": viewport["height"],
            },
        )

    async def stop(self) -> None:
        if self.cdp is None:
            return
        try:
            await self.cdp.send("Page.stopScreencast")
            await self.cdp.detach()
        except Exception:
            pass  # page already closed
        self.cdp = None

    def _on_frame(self, params: dict[str, Any]) -> None:
        meta = params.get("metadata", {})
        frame = {
            "type": "frame",
            "data": params["data"],
            "width": meta.get("deviceWidth"),
            "height": meta.get("deviceHeight"),
        }
        self.last_frame = frame
        task = asyncio.ensure_future(self._ack_and_send(params["sessionId"], frame))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _ack_and_send(self, session_id: int, frame: dict[str, Any]) -> None:
        if self.cdp is not None:
            try:
                await self.cdp.send("Page.screencastFrameAck", {"sessionId": session_id})
            except Exception:
                return
        await self.sink(frame)

    async def dispatch_input(self, event: dict[str, Any]) -> None:
        """Forward one mouse or keyboard event from the UI. Coordinates are CSS pixels."""
        if self.cdp is None:
            return
        kind = event.get("kind")
        modifiers = int(event.get("modifiers", 0))
        if kind == "mouse":
            etype = event.get("event")
            if etype not in _MOUSE_TYPES:
                return
            params: dict[str, Any] = {
                "type": etype,
                "x": float(event.get("x", 0)),
                "y": float(event.get("y", 0)),
                "modifiers": modifiers,
                "button": event.get("button", "none"),
                "clickCount": int(event.get("clickCount", 0)),
            }
            if etype == "mouseWheel":
                params["deltaX"] = float(event.get("deltaX", 0))
                params["deltaY"] = float(event.get("deltaY", 0))
            await self.cdp.send("Input.dispatchMouseEvent", params)
        elif kind == "key":
            key = str(event.get("key", ""))
            etype = "keyDown" if event.get("event") == "keyDown" else "keyUp"
            params = {
                "type": etype,
                "key": key,
                "code": event.get("code", ""),
                "modifiers": modifiers,
            }
            if key in _KEY_CODES:
                params["windowsVirtualKeyCode"] = _KEY_CODES[key]
                if key == "Enter" and etype == "keyDown":
                    params["text"] = "\r"
            elif (
                etype == "keyDown" and len(key) == 1 and not modifiers & 6
            ):  # CDP bits: alt=1 ctrl=2 meta=4 shift=8
                params["text"] = key
            await self.cdp.send("Input.dispatchKeyEvent", params)
