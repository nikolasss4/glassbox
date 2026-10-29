"""Provider registry. A provider spec is a model name/alias, `random`, or `replay:<dir>`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from glassbox.providers.base import Decision, Provider

_EXTRA: dict[str, Callable[[], Provider]] = {}


def register(name: str, factory: Callable[[], Provider]) -> None:
    """Let other modules (e.g. the eval suite's oracle) add named providers."""
    _EXTRA[name] = factory


def get_provider(spec: str, *, effort: str = "medium") -> Provider:
    if spec in _EXTRA:
        return _EXTRA[spec]()
    if spec == "random":
        from glassbox.providers.random_baseline import RandomProvider

        return RandomProvider()
    if spec.startswith("replay:"):
        from glassbox.providers.replay import ReplayProvider

        return ReplayProvider(Path(spec.removeprefix("replay:")))
    from glassbox.providers.anthropic import AnthropicProvider

    return AnthropicProvider(spec, effort=effort)


__all__ = ["Decision", "Provider", "get_provider", "register"]
