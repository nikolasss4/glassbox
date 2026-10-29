"""FastAPI app: start runs, stream them live over WebSocket, serve traces and the UI."""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import Browser, BrowserContext, async_playwright
from pydantic import BaseModel, Field

from glassbox.agent import Agent, AgentConfig, RunControl, Step
from glassbox.browser import VIEWPORT, BrowserSession
from glassbox.config import DEFAULT_MODEL
from glassbox.live import Screencast
from glassbox.providers import get_provider
from glassbox.sitesrv import mount_sites
from glassbox.trace import TraceStore, TraceWriter

FRONTEND_DIST = Path(
    os.environ.get("GLASSBOX_FRONTEND_DIST", Path(__file__).parents[2] / "frontend" / "dist")
)


class RunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    start_url: str | None = None
    task_id: str | None = None
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    vision: bool = False
    max_steps: int = Field(default=25, ge=1, le=100)


@dataclass
class LiveRun:
    writer: TraceWriter
    control: RunControl
    context: BrowserContext
    screencast: Screencast | None = None
    task: asyncio.Task[None] | None = None
    subscribers: set[WebSocket] = field(default_factory=set)
    finished: bool = False

    async def broadcast(self, msg: dict[str, Any]) -> None:
        dead = []
        for ws in list(self.subscribers):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.subscribers.discard(ws)

    def status(self) -> str:
        if self.finished:
            return "finished"
        return "paused" if self.control.paused else "running"


def step_message(run_id: str, step: Step, doc_step: dict[str, Any]) -> dict[str, Any]:
    data = step.model_dump(mode="json", exclude={"raw"})
    data["thinking"] = (step.raw or {}).get("thinking", "")
    data["cost_usd"] = step.usage.cost(step.model)
    if shot := doc_step.get("screenshot"):
        data["screenshot_url"] = f"/api/runs/{run_id}/assets/{shot}"
    return {"type": "step", "step": data}


def create_app(runs_dir: Path | None = None, *, headless: bool = True) -> FastAPI:
    store = TraceStore(runs_dir or Path(os.environ.get("GLASSBOX_RUNS_DIR", "runs")))
    live: dict[str, LiveRun] = {}
    state: dict[str, Browser] = {}

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with async_playwright() as pw:
            state["browser"] = await pw.chromium.launch(headless=headless)
            yield
            for run in live.values():
                run.control.cancel()
            await asyncio.gather(*(r.task for r in live.values() if r.task), return_exceptions=True)
            await state["browser"].close()

    app = FastAPI(title="glassbox", lifespan=lifespan)
    mount_sites(app)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runs")
    async def list_runs() -> list[dict[str, Any]]:
        runs = store.list()
        for r in runs:
            if r["id"] in live:
                r["status"] = live[r["id"]].status()
        return runs

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        try:
            return store.load(run_id)
        except FileNotFoundError:
            raise HTTPException(404, "run not found") from None

    @app.get("/api/runs/{run_id}/assets/{name}")
    async def get_asset(run_id: str, name: str) -> FileResponse:
        try:
            path = store.asset(run_id, name)
        except FileNotFoundError:
            raise HTTPException(404, "asset not found") from None
        if not path.is_file():
            raise HTTPException(404, "asset not found")
        return FileResponse(path, headers={"Cache-Control": "max-age=86400, immutable"})

    @app.post("/api/runs")
    async def start_run(req: RunRequest) -> dict[str, str]:
        try:
            provider = get_provider(req.model, effort=req.effort)
        except Exception as e:
            raise HTTPException(400, f"cannot create provider: {e}") from None
        context = await state["browser"].new_context(viewport=VIEWPORT)  # type: ignore[arg-type]
        page = await context.new_page()
        writer = store.create(
            {
                "goal": req.goal,
                "start_url": req.start_url,
                "task_id": req.task_id,
                "provider": provider.name,
                "config": req.model_dump(),
            }
        )
        run = LiveRun(writer=writer, control=RunControl(), context=context)
        run.screencast = Screencast(page, run.broadcast)
        await run.screencast.start()

        async def on_event(kind: str, data: dict[str, Any]) -> None:
            await writer.on_event(kind, data)
            if kind == "step":
                await run.broadcast(
                    step_message(writer.run_id, data["step"], writer.doc["steps"][-1])
                )
            elif kind == "run_finished":
                await run.broadcast({"type": "run_finished", "result": data})

        agent = Agent(
            provider=provider,
            browser=BrowserSession(page),
            config=AgentConfig(max_steps=req.max_steps, vision=req.vision),
            control=run.control,
            on_event=on_event,
        )

        async def drive() -> None:
            try:
                await agent.run(req.goal, req.start_url, task_id=req.task_id)
            finally:
                run.finished = True
                await run.broadcast({"type": "status", "status": "finished"})
                if run.screencast:
                    await run.screencast.stop()
                await context.close()

        run.task = asyncio.create_task(drive())
        live[writer.run_id] = run
        return {"id": writer.run_id}

    @app.websocket("/ws/runs/{run_id}")
    async def run_socket(ws: WebSocket, run_id: str) -> None:
        await ws.accept()
        run = live.get(run_id)
        if run is None:
            await ws.send_json({"type": "error", "message": "run is not live; load its trace"})
            await ws.close()
            return
        run.subscribers.add(ws)
        doc = run.writer.doc
        await ws.send_json({"type": "hello", "run": {k: v for k, v in doc.items() if k != "steps"}})
        await ws.send_json({"type": "status", "status": run.status()})
        if run.screencast and run.screencast.last_frame:
            await ws.send_json(run.screencast.last_frame)
        try:
            while True:
                msg = await ws.receive_json()
                await handle_client_message(run, msg)
        except WebSocketDisconnect:
            pass
        finally:
            run.subscribers.discard(ws)

    async def handle_client_message(run: LiveRun, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if run.finished:
            return
        if kind == "pause" and not run.control.paused:
            run.control.pause()
            run.writer.add_event("takeover", {})
            await run.broadcast({"type": "status", "status": "paused"})
        elif kind == "resume" and run.control.paused:
            note = str(msg.get("note", ""))[:1000]
            run.writer.add_event("resume", {"note": note})
            run.control.resume(note)
            await run.broadcast({"type": "status", "status": "running"})
        elif kind == "cancel":
            run.control.cancel()
        elif kind == "input" and run.control.paused and run.screencast:
            # Human input is only forwarded during a takeover, never while the agent drives.
            await run.screencast.dispatch_input(msg)

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="ui")

    return app
