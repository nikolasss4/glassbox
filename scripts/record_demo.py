"""Record the README demo GIF by driving the real UI with Playwright.

    uv run python scripts/record_demo.py --model claude-sonnet-5-5 --task shop-checkout-coupon

Starts the app in-process on a free port, runs the task from the "new run" form, captures
the live view, timeline and a short replay scrub, then writes docs/demo.gif. With
`--model oracle` the scripted solution is slowed down so the GIF is watchable.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import socket
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from PIL import Image
from playwright.async_api import Page, async_playwright

from glassbox.browser import Observation
from glassbox.evals.runner import OracleProvider
from glassbox.providers import register
from glassbox.providers.base import Decision
from glassbox.server import create_app


class SlowOracle(OracleProvider):
    """The oracle with human-watchable pacing."""

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        await asyncio.sleep(0.9)
        return await super().decide(obs, feedback)


def serve(runs: Path) -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(runs), port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}"


async def capture(page: Page, frames: list[Image.Image], seconds: float, fps: float = 5) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        t0 = time.monotonic()
        png = await page.screenshot()
        frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
        await asyncio.sleep(max(0, 1 / fps - (time.monotonic() - t0)))


async def record(base: str, model: str, task: str, run_seconds: float) -> list[Image.Image]:
    frames: list[Image.Image] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1440, "height": 860})).new_page()
        await page.goto(f"{base}/#/")
        await page.wait_for_timeout(600)
        await page.select_option("select >> nth=0", task)
        await page.select_option("select >> nth=1", model)
        await capture(page, frames, 1.2)
        await page.click("text=Start run")
        await capture(page, frames, run_seconds)
        # Scrub back through the recording.
        n = await page.locator("ol > li").count() - 1
        for i in range(0, max(n, 1), 2):
            await page.locator("input.scrubber").fill(str(i))
            await capture(page, frames, 0.6)
        await browser.close()
    return frames


def write_gif(frames: list[Image.Image], out: Path) -> None:
    small = [f.resize((1080, 645), Image.Resampling.LANCZOS) for f in frames]
    small[0].save(out, save_all=True, append_images=small[1:], duration=200, loop=0, optimize=True)
    print(f"wrote {out} ({len(small)} frames, {out.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--task", default="shop-checkout-coupon")
    ap.add_argument("--seconds", type=float, default=14.0, help="how long to film the live run")
    ap.add_argument("--out", type=Path, default=Path("docs/demo.gif"))
    args = ap.parse_args()
    register("oracle", SlowOracle)  # registry entries take precedence over built-ins
    model = args.model
    with tempfile.TemporaryDirectory() as runs:
        base = serve(Path(runs))
        frames = asyncio.run(record(base, model, args.task, args.seconds))
    write_gif(frames, args.out)


if __name__ == "__main__":
    main()
