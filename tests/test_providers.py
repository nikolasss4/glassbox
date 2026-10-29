from pathlib import Path
from typing import Any

import pytest
from anthropic.types.beta import BetaMessage
from playwright.async_api import Browser

from glassbox.agent import Agent
from glassbox.browser import BrowserSession, Observation
from glassbox.providers import get_provider
from glassbox.providers.anthropic import FALLBACK_BETA, AnthropicProvider
from glassbox.providers.random_baseline import RandomProvider
from glassbox.providers.replay import FixtureDrift, RecordingProvider, ReplayProvider
from glassbox.providers.scripted import S, ScriptedProvider
from glassbox.sitesrv import SiteServer

OBS = Observation(url="http://x/", title="t", text='URL: http://x/\n[e1] button "Go"\n', refs=1)


def _msg(content: list[dict[str, Any]], stop: str = "tool_use") -> BetaMessage:
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": 50,
                "cache_creation_input_tokens": 0,
            },
        }
    )


class FakeClient:
    def __init__(self, replies: list[BetaMessage]) -> None:
        self.replies = replies
        self.calls: list[dict[str, Any]] = []
        self.beta = self
        self.messages = self

    async def create(self, **kwargs: Any) -> BetaMessage:
        # Snapshot the messages list: the provider keeps appending to it.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


def _tool_use(name: str, inp: dict[str, Any], id: str = "tu_1") -> dict[str, Any]:
    return {"type": "tool_use", "id": id, "name": name, "input": inp}


async def test_anthropic_provider_builds_append_only_history() -> None:
    client = FakeClient(
        [
            _msg([_tool_use("click", {"ref": "e1", "reason": "press go"})]),
            _msg([_tool_use("done", {"success": True, "answer": "42", "reason": "found"}, "tu_2")]),
        ]
    )
    p = AnthropicProvider("sonnet", client=client)
    p.start("find the answer")
    d1 = await p.decide(OBS, None)
    assert d1.action.name == "click" and d1.action.args == {"ref": "e1"}
    assert d1.thought == "press go"
    assert d1.usage.input_tokens == 100 and d1.usage.cache_read_tokens == 50
    d2 = await p.decide(OBS, "click e1: ok")
    assert d2.action.args["answer"] == "42"

    first, second = client.calls
    assert first["model"] == "claude-sonnet-5-5"
    assert first["betas"] == [FALLBACK_BETA] and first["fallbacks"] == "default"
    assert first["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    # The second request extends the first one; nothing earlier was rewritten.
    assert second["messages"][: len(first["messages"])] == first["messages"]
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tu_1"
    assert "click e1: ok" in tool_result["content"][-1]["text"]


async def test_anthropic_provider_nudges_when_no_tool_call() -> None:
    client = FakeClient(
        [
            _msg([{"type": "text", "text": "I think I should click."}], stop="end_turn"),
            _msg([_tool_use("click", {"ref": "e1", "reason": "ok"})]),
        ]
    )
    p = AnthropicProvider("haiku", client=client)
    p.start("goal")
    d = await p.decide(OBS, None)
    assert d.action.name == "click"
    assert d.usage.input_tokens == 200  # both calls are billed
    assert "betas" not in client.calls[0]  # no server-side fallback for Haiku
    assert client.calls[1]["messages"][-1]["content"].startswith("Respond with exactly one tool")


async def test_anthropic_provider_handles_refusal() -> None:
    client = FakeClient([_msg([], stop="refusal")])
    p = AnthropicProvider("opus", client=client)
    p.start("goal")
    d = await p.decide(OBS, None)
    assert d.action.name == "done" and d.action.args["success"] is False


async def test_random_baseline_is_seeded_per_task() -> None:
    a, b = RandomProvider(), RandomProvider()
    a.start("g", "task-1")
    b.start("g", "task-1")
    assert (await a.decide(OBS, None)).action == (await b.decide(OBS, None)).action


def test_registry() -> None:
    assert get_provider("random").name == "random"
    assert get_provider("oracle").name == "oracle"
    assert get_provider("opus", effort="low").name == "claude-opus-5-5"


async def test_record_then_replay(sites: SiteServer, browser: Browser, tmp_path: Path) -> None:
    script = [
        S("type", "Username", args={"text": "alice", "submit": False}),
        S("type", "Password", args={"text": "sunflower-42", "submit": True}),
        S("done", args={"success": True, "answer": "ok"}),
    ]
    url = f"{sites.base_url}/sites/login/"

    async def run(provider) -> Agent:  # type: ignore[no-untyped-def]
        page = await (await browser.new_context()).new_page()
        agent = Agent(provider=provider, browser=BrowserSession(page))
        await agent.run("log in", url, task_id="login-demo")
        return agent

    recorded = await run(RecordingProvider(ScriptedProvider(script), tmp_path))
    replayed = await run(ReplayProvider(tmp_path))
    assert [s.action for s in replayed.steps] == [s.action for s in recorded.steps]
    assert replayed.browser.page.url.endswith("welcome.html")

    # Same fixture against a different starting page must fail loudly.
    page = await (await browser.new_context()).new_page()
    await page.goto(f"{sites.base_url}/sites/shop/")
    provider = ReplayProvider(tmp_path)
    provider.start("log in", "login-demo")
    with pytest.raises(FixtureDrift):
        await provider.decide(await BrowserSession(page).observe(), None)
