"""Model presets and prices used for cost accounting."""

from __future__ import annotations

from dataclasses import dataclass

# Short names accepted anywhere a model is expected (`--model sonnet`).
MODEL_ALIASES = {
    "sonnet": "claude-sonnet-5-5",  # default
    "opus": "claude-opus-5-5",  # "strong"
    "haiku": "claude-haiku-5-5",  # "cheap"
}
DEFAULT_MODEL = MODEL_ALIASES["sonnet"]


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float

    @property
    def cache_write(self) -> float:
        return self.input * 1.25  # 5-minute cache writes


PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(input=4.00, output=20.00, cache_read=0.20),
    "claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_read=0.20),
    "claude-haiku-5-5": Price(input=0.10, output=0.50, cache_read=0.01),
}


def resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name, name)
