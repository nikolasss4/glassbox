"""Token usage and cost accounting."""

from __future__ import annotations

from pydantic import BaseModel

from glassbox.config import PRICES


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )

    def cost(self, model: str) -> float:
        """USD cost; unknown models (baselines, scripted runs) cost nothing."""
        price = PRICES.get(model)
        if price is None:
            return 0.0
        return (
            self.input_tokens * price.input
            + self.output_tokens * price.output
            + self.cache_read_tokens * price.cache_read
            + self.cache_write_tokens * price.cache_write
        ) / 1_000_000
