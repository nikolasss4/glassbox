import asyncio

from playwright.async_api import Browser

from glassbox.agent import Agent, AgentConfig, RunControl
from glassbox.browser import BrowserSession
from glassbox.providers.scripted import S, ScriptedProvider, find_ref
from glassbox.sitesrv import SiteServer

LOGIN = [
    S("type", "Username", args={"text": "alice", "submit": False}),
    S("type", "Password", args={"text": "sunflower-42", "submit": True}),
    S("done", args={"success": True, "answer": "logged in"}),
]


async def _agent(browser: Browser, provider, **cfg) -> Agent:  # type: ignore[no-untyped-def]
    ctx = await browser.new_context()
    page = await ctx.new_page()
    return Agent(provider=provider, browser=BrowserSession(page), config=AgentConfig(**cfg))


async def test_scripted_login(sites: SiteServer, browser: Browser) -> None:
    agent = await _agent(browser, ScriptedProvider(LOGIN))
    result = await agent.run("log in as alice", f"{sites.base_url}/sites/login/")
    assert result.stop_reason == "done"
    assert result.success_claimed
    assert agent.browser.page.url.endswith("/sites/login/welcome.html")
    assert [s.action.name for s in agent.steps] == ["type", "type", "done"]
    assert all(s.result.ok for s in agent.steps)
    assert agent.steps[0].screenshot


async def test_step_budget(sites: SiteServer, browser: Browser) -> None:
    wait = [S("wait", args={"seconds": 0.5})] * 10
    agent = await _agent(browser, ScriptedProvider(wait), max_steps=3)
    result = await agent.run("wait forever", f"{sites.base_url}/sites/")
    assert result.stop_reason == "max_steps"
    assert result.steps == 3


async def test_covered_element_reports_overlay(sites: SiteServer, browser: Browser) -> None:
    script = [S("click", "Download Q3 report"), S("done", args={"success": False, "answer": ""})]
    agent = await _agent(browser, ScriptedProvider(script))
    await agent.run("download", f"{sites.base_url}/sites/traps/cookie.html")
    first = agent.steps[0].result
    assert not first.ok
    assert "covering" in first.message


async def test_snapshot_is_deterministic(sites: SiteServer, browser: Browser) -> None:
    ctx = await browser.new_context()
    page = await ctx.new_page()
    session = BrowserSession(page)
    await page.goto(f"{sites.base_url}/sites/shop/")
    a = await session.observe()
    await page.reload()
    b = await session.observe()
    assert a.digest == b.digest
    assert find_ref(a.text, "Search products") is not None
    assert "(covered" not in a.text


async def test_takeover_mid_step_skips_stale_action(sites: SiteServer, browser: Browser) -> None:
    control = RunControl()

    class SlowProvider(ScriptedProvider):
        async def decide(self, obs, feedback):  # type: ignore[no-untyped-def]
            if self._i == 0:
                control.pause()  # human grabs control while the model "thinks"
                asyncio.get_running_loop().call_later(0.2, control.resume, "I logged in myself")
            return await super().decide(obs, feedback)

    agent = await _agent(browser, SlowProvider(LOGIN))
    agent.control = control
    await agent.run("log in", f"{sites.base_url}/sites/login/")
    first = agent.steps[0]
    assert first.human_note == "I logged in myself"
    assert not first.result.ok and "human operator" in first.result.message


def test_digest_ignores_layout_annotations() -> None:
    from glassbox.browser import Observation

    a = Observation("u", "t", 'Scroll: 0 of 455px\n[e1] button "Go" (below viewport)\n', 1)
    b = Observation("u", "t", 'Scroll: 0 of 470px\n[e1] button "Go"\n', 1)
    c = Observation("u", "t", 'Scroll: 0 of 455px\n[e1] button "Stop"\n', 1)
    assert a.digest == b.digest != c.digest
    d = Observation("http://127.0.0.1:5001/x", "t", "URL: http://127.0.0.1:5001/x\n", 0)
    e = Observation("http://127.0.0.1:6002/x", "t", "URL: http://127.0.0.1:6002/x\n", 0)
    assert d.digest == e.digest
