"""prompt -> validated JSON dict, rejecting + retrying on bad output (plan §B1)."""
from __future__ import annotations

import json
import re
from typing import Callable

from src.config import MAX_RETRIES
from src.llm.client import LLMError


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def extract(chat: Callable[[str, str], str], system: str, user: str, required_keys: list[str]) -> dict:
    last = None
    for _ in range(MAX_RETRIES + 1):
        try:
            out = _extract_json(chat(system, user))
            if all(k in out for k in required_keys):
                return out
            last = f"missing keys (got {list(out)})"
        except LLMError as e:
            last = str(e)
        except Exception as e:
            last = str(e)
    raise LLMError(f"structured output failed after {MAX_RETRIES} retries: {last}")
