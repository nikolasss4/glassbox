"""Playwright wrapper: page observation (snapshot + optional screenshot) and action execution."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

from glassbox.actions import Action, ActionResult

SNAPSHOT_JS = (Path(__file__).parent / "snapshot.js").read_text()
VIEWPORT = {"width": 1280, "height": 800}


@dataclass
class Observation:
    url: str
    title: str
    text: str
    refs: int
    screenshot: bytes | None = None

    @property
    def digest(self) -> str:
        """Stable hash of what the model saw; replay fixtures use it to detect drift."""
        return hashlib.sha256(self.text.encode()).hexdigest()[:16]


class BrowserSession:
    """Owns one Playwright page and translates agent actions into browser operations."""

    def __init__(
        self,
        page: Page,
        *,
        allowed_origins: list[str] | None = None,
        action_timeout_ms: int = 4000,
        retries: int = 2,
        max_snapshot_chars: int = 14000,
    ) -> None:
        self.page = page
        self.allowed_origins = allowed_origins
        self.action_timeout_ms = action_timeout_ms
        self.retries = retries
        self.max_snapshot_chars = max_snapshot_chars

    async def observe(self, *, screenshot: bool = False) -> Observation:
        await self._settle()
        for attempt in range(3):
            try:
                data = await self.page.evaluate(SNAPSHOT_JS, self.max_snapshot_chars)
                break
            except PlaywrightError:
                # The page navigated mid-evaluate; wait for the new document and try again.
                if attempt == 2:
                    raise
                await self._settle()
        shot = await self.screenshot() if screenshot else None
        return Observation(
            url=self.page.url,
            title=await self.page.title(),
            text=data["text"],
            refs=data["refs"],
            screenshot=shot,
        )

    async def screenshot(self, quality: int = 70) -> bytes:
        return await self.page.screenshot(type="jpeg", quality=quality)

    async def execute(self, action: Action) -> ActionResult:
        try:
            handler = getattr(self, f"_do_{action.name}")
            result: ActionResult = await handler(**action.args)
        except TypeError as e:
            return ActionResult(ok=False, message=f"Bad arguments for {action.name}: {e}")
        except PlaywrightError as e:
            return ActionResult(ok=False, message=_short_error(e))
        await self._settle()
        return result

    # --- helpers -----------------------------------------------------------------

    async def _settle(self) -> None:
        """Give the page a moment to finish navigation and quick re-renders."""
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            await self.page.wait_for_load_state("networkidle", timeout=1500)
        except PlaywrightTimeout:
            pass
        await asyncio.sleep(0.15)

    def _locator(self, ref: str):  # type: ignore[no-untyped-def]
        return self.page.locator(f'[data-gb-ref="{ref}"]')

    async def _with_retries(self, ref: str, op: str, fn) -> ActionResult:  # type: ignore[no-untyped-def]
        """Run a locator operation, retrying transient failures (animations, re-renders)."""
        loc = self._locator(ref)
        if await loc.count() == 0:
            return ActionResult(
                ok=False,
                message=f"No element with ref {ref} on the current page. Use a ref from the "
                "latest snapshot.",
            )
        last = ""
        for attempt in range(self.retries + 1):
            try:
                await fn(loc)
                return ActionResult(ok=True, message=f"{op} {ref}: ok")
            except PlaywrightTimeout as e:
                last = _short_error(e)
                if "intercepts pointer events" in str(e):
                    return ActionResult(
                        ok=False,
                        message=f"{op} {ref} failed: another element (an overlay, banner or "
                        "dialog) is covering it.",
                    )
            except PlaywrightError as e:
                last = _short_error(e)
            if attempt < self.retries:
                await asyncio.sleep(0.4 * (attempt + 1))
        return ActionResult(ok=False, message=f"{op} {ref} failed: {last}")

    # --- actions -----------------------------------------------------------------

    async def _do_navigate(self, url: str) -> ActionResult:
        target = urlparse(url)
        if not target.scheme:
            url = f"{urlparse(self.page.url).scheme}://{urlparse(self.page.url).netloc}/{url.lstrip('/')}"
            target = urlparse(url)
        if self.allowed_origins is not None:
            origin = f"{target.scheme}://{target.netloc}"
            if origin not in self.allowed_origins:
                return ActionResult(ok=False, message=f"Navigation to {origin} is not allowed.")
        await self.page.goto(url, timeout=15000)
        return ActionResult(ok=True, message=f"Opened {url}")

    async def _do_click(self, ref: str) -> ActionResult:
        return await self._with_retries(
            ref, "click", lambda loc: loc.click(timeout=self.action_timeout_ms)
        )

    async def _do_type(self, ref: str, text: str, submit: bool = False) -> ActionResult:
        async def op(loc) -> None:  # type: ignore[no-untyped-def]
            await loc.fill(text, timeout=self.action_timeout_ms)
            if submit:
                await loc.press("Enter", timeout=self.action_timeout_ms)

        result = await self._with_retries(ref, "type into", op)
        if result.ok:
            result.message = f"Typed {text!r} into {ref}" + (" and pressed Enter" if submit else "")
        return result

    async def _do_select_option(self, ref: str, option: str) -> ActionResult:
        result = await self._with_retries(
            ref,
            "select",
            lambda loc: loc.select_option(label=option, timeout=self.action_timeout_ms),
        )
        if result.ok:
            result.message = f"Selected {option!r} in {ref}"
        return result

    async def _do_press_key(self, key: str) -> ActionResult:
        await self.page.keyboard.press(key)
        return ActionResult(ok=True, message=f"Pressed {key}")

    async def _do_scroll(self, direction: str) -> ActionResult:
        dy = VIEWPORT["height"] * 0.8 * (-1 if direction == "up" else 1)
        await self.page.mouse.move(VIEWPORT["width"] / 2, VIEWPORT["height"] / 2)
        await self.page.mouse.wheel(0, dy)
        await asyncio.sleep(0.3)
        return ActionResult(ok=True, message=f"Scrolled {direction}")

    async def _do_wait(self, seconds: float) -> ActionResult:
        seconds = max(0.5, min(float(seconds), 5.0))
        await asyncio.sleep(seconds)
        return ActionResult(ok=True, message=f"Waited {seconds:g}s")

    async def _do_extract(self, data: str) -> ActionResult:
        return ActionResult(ok=True, message="Noted.")

    async def _do_done(self, success: bool, answer: str) -> ActionResult:
        return ActionResult(ok=True, message="Task finished.")


def _short_error(e: Exception) -> str:
    first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return first[:300]
