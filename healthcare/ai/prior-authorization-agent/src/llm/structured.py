"""prompt -> validated Pydantic, with reject-and-retry for small local models.

Small open models are less reliable at JSON tool calling than hosted models, so every
structured call validates against the Pydantic contract and retries (max LLM_MAX_RETRIES)
before raising StructuredError, which the agents turn into a human escalation. First-try
success and failures are tracked for the reliability metric (planv2 B5)."""
from __future__ import annotations
from dataclasses import dataclass, field

from src import config
from src.llm.client import get_llm


class StructuredError(RuntimeError):
    """Raised when the model can't produce contract-valid output within the retry budget."""


@dataclass
class _Stats:
    calls: int = 0
    first_try_ok: int = 0
    retried_ok: int = 0
    failed: int = 0

    def reset(self) -> None:
        self.calls = self.first_try_ok = self.retried_ok = self.failed = 0

    @property
    def first_try_rate(self) -> float:
        return self.first_try_ok / self.calls if self.calls else 0.0


STATS = _Stats()


def extract(schema, prompt: str):
    """Return a validated `schema` instance, retrying on invalid model output."""
    STATS.calls += 1
    runnable = get_llm().with_structured_output(schema)
    last_err: Exception | None = None
    for attempt in range(config.LLM_MAX_RETRIES + 1):
        try:
            out = runnable.invoke(prompt)
            if out is None:
                raise ValueError("model returned no structured output")
            if attempt == 0:
                STATS.first_try_ok += 1
            else:
                STATS.retried_ok += 1
            return out
        except Exception as e:                       # invalid JSON / schema mismatch / transport
            last_err = e
    STATS.failed += 1
    raise StructuredError(f"structured output failed after {config.LLM_MAX_RETRIES} retries: {last_err}")
