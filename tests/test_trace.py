from pathlib import Path

import pytest
from playwright.async_api import Browser

from glassbox.agent import Agent
from glassbox.browser import BrowserSession
from glassbox.providers.scripted import S, ScriptedProvider
from glassbox.sitesrv import SiteServer
from glassbox.trace import TraceStore


async def test_trace_roundtrip(sites: SiteServer, browser: Browser, tmp_path: Path) -> None:
    store = TraceStore(tmp_path)
    writer = store.create({"goal": "log in", "provider": "scripted"})
    page = await (await browser.new_context()).new_page()
    script = [
        S("type", "Username", args={"text": "alice", "submit": False}),
        S("done", args={"success": False, "answer": "stopped"}),
    ]
    agent = Agent(
        provider=ScriptedProvider(script), browser=BrowserSession(page), on_event=writer.on_event
    )
    await agent.run("log in", f"{sites.base_url}/sites/login/")

    doc = store.load(writer.run_id)
    assert doc["status"] == "finished"
    assert doc["result"]["stop_reason"] == "done"
    assert [s["action"]["name"] for s in doc["steps"]] == ["type", "done"]
    assert "[e1]" in doc["steps"][0]["observation"]
    assert store.asset(writer.run_id, doc["steps"][0]["screenshot"]).stat().st_size > 1000

    [summary] = store.list()
    assert summary["id"] == writer.run_id and summary["n_steps"] == 2


def test_asset_paths_cannot_escape(tmp_path: Path) -> None:
    store = TraceStore(tmp_path)
    w = store.create({"goal": "x"})
    with pytest.raises(FileNotFoundError):
        store.asset(w.run_id, "../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        store.load("../x")
