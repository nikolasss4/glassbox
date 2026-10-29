"""Claude via the Anthropic Messages API, one tool call per step."""

from __future__ import annotations

import base64
import time
from typing import Any

import anthropic

from glassbox.actions import TOOL_NAMES, TOOLS, Action, action_from_tool_call
from glassbox.browser import Observation
from glassbox.config import resolve_model
from glassbox.prompts import SYSTEM_PROMPT, format_observation, format_task
from glassbox.providers.base import Decision, Provider
from glassbox.usage import Usage

# Server-side refusal fallback ("default" routes by refusal category). Haiku has none.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
_MAX_NUDGES = 2


class AnthropicProvider(Provider):
    def __init__(
        self,
        model: str,
        *,
        effort: str = "medium",
        max_tokens: int = 8000,
        client: Any | None = None,
    ) -> None:
        self.name = resolve_model(model)
        self.effort = effort
        self.max_tokens = max_tokens
        self.client = client or anthropic.AsyncAnthropic(max_retries=4, timeout=120.0)
        self.messages: list[dict[str, Any]] = []
        self._pending_tool_use: str | None = None
        self._goal = ""

    def start(self, goal: str, task_id: str | None = None) -> None:
        # History is append-only for the whole run: earlier turns (including thinking
        # blocks) are sent back unchanged, which keeps the prompt cache warm.
        self.messages = []
        self._pending_tool_use = None
        self._goal = goal

    async def decide(self, obs: Observation, feedback: str | None) -> Decision:
        content = _observation_blocks(obs, feedback)
        if self._pending_tool_use is None:
            first = [{"type": "text", "text": format_task(self._goal)}, *content]
            self.messages.append({"role": "user", "content": first})
        else:
            result = {
                "type": "tool_result",
                "tool_use_id": self._pending_tool_use,
                "content": content,
            }
            self.messages.append({"role": "user", "content": [result]})
            self._pending_tool_use = None

        usage = Usage()
        latency = 0.0
        served_model = self.name
        for _ in range(_MAX_NUDGES + 1):
            t0 = time.monotonic()
            response = await self._create()
            latency += time.monotonic() - t0
            usage = usage + _usage(response.usage)
            served_model = response.model or self.name
            self.messages.append({"role": "assistant", "content": response.content})

            raw = _raw(response)
            if response.stop_reason == "refusal":
                action = Action(
                    name="done",
                    args={"success": False, "answer": "The model declined this request."},
                )
                return Decision(
                    action=action, usage=usage, model=served_model, latency_s=latency, raw=raw
                )

            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_use is not None:
                self._pending_tool_use = tool_use.id
                if tool_use.name not in TOOL_NAMES:
                    action = Action(name="wait", args={"seconds": 0.5}, reason="unknown tool")
                else:
                    action = action_from_tool_call(tool_use.name, dict(tool_use.input))
                return Decision(
                    action=action,
                    thought=action.reason or raw.get("text", ""),
                    usage=usage,
                    model=served_model,
                    latency_s=latency,
                    raw=raw,
                )
            # The model answered in prose (or ran out of tokens). Ask for a tool call.
            self.messages.append(
                {"role": "user", "content": "Respond with exactly one tool call to continue."}
            )

        action = Action(
            name="done", args={"success": False, "answer": "Model stopped producing tool calls."}
        )
        return Decision(action=action, usage=usage, model=served_model, latency_s=latency)

    async def _create(self) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.name,
            "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": SYSTEM_PROMPT}],
            "tools": TOOLS,
            "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self.effort},
            # Automatic caching: each step re-reads the whole history from cache.
            "cache_control": {"type": "ephemeral"},
            "messages": self.messages,
        }
        if self.name in _FALLBACK_MODELS:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return await self.client.beta.messages.create(**kwargs)


def _observation_blocks(obs: Observation, feedback: str | None) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if obs.screenshot:
        data = base64.standard_b64encode(obs.screenshot).decode()
        blocks.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
            }
        )
    blocks.append({"type": "text", "text": format_observation(obs, feedback)})
    return blocks


def _usage(u: Any) -> Usage:
    return Usage(
        input_tokens=u.input_tokens or 0,
        output_tokens=u.output_tokens or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
    )


def _raw(response: Any) -> dict[str, Any]:
    thinking = [b.thinking for b in response.content if b.type == "thinking" and b.thinking]
    text = [b.text for b in response.content if b.type == "text"]
    return {
        "id": response.id,
        "model": response.model,
        "stop_reason": response.stop_reason,
        "thinking": "\n".join(thinking),
        "text": "\n".join(text),
    }
