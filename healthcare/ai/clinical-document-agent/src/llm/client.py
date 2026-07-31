"""get_llm() factory. One place to switch provider (plan §B1).

Kept dependency-light: the call goes over stdlib HTTPS to the OpenAI-compatible endpoint, so
the package runs without langchain installed. Agents take an injectable `llm` callable, so the
pipeline and tests can run fully offline.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from src import config


class LLMError(RuntimeError):
    pass


def get_llm() -> Callable[[str, str], str]:
    """Return chat(system, user) -> content string for the configured provider."""
    if config.LLM_PROVIDER == "ollama":
        base, key, model = config.OLLAMA_BASE_URL, None, config.MODEL_NAME
    else:
        base, key, model = config.NVIDIA_BASE_URL, config.NVIDIA_API_KEY, config.MODEL_NAME
        if not key:
            raise LLMError("NVIDIA_API_KEY is not set. Configure .env or use LLM_PROVIDER=ollama.")

    def chat(system: str, user: str) -> str:
        body = json.dumps({
            "model": model, "temperature": 0.0, "max_tokens": 900,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            req = urllib.request.Request(f"{base.rstrip('/')}/chat/completions", data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
            return payload["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}")          # never surface the key/body
        except Exception as e:
            raise LLMError(str(e))

    return chat
