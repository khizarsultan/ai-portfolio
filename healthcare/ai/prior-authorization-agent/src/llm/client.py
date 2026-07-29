"""The single LLM factory. Every agent gets its model from here — swap backends in one place.

  LLM_BACKEND=nvidia  -> NVIDIA NIM hosted open-weight models (build.nvidia.com, free tier,
                         OpenAI-compatible). Data leaves the machine, so agents send a
                         Safe-Harbor-redacted view of the case (see compliance.redact).
  LLM_BACKEND=ollama  -> fully local open-weight model, zero egress, no API key, no BAA.
"""
from __future__ import annotations
from functools import lru_cache

from src import config


@lru_cache(maxsize=1)
def get_llm():
    if config.LLM_BACKEND == "nvidia":
        if not config.NVIDIA_API_KEY:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Get a free key at build.nvidia.com and add it to "
                ".env, or set LLM_BACKEND=ollama to run locally.")
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        return ChatNVIDIA(
            model=config.MODEL_NAME,
            api_key=config.NVIDIA_API_KEY,
            base_url=config.NVIDIA_BASE_URL,
            temperature=config.TEMPERATURE,
            max_tokens=1500,
        )
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=config.MODEL_NAME,
        base_url=config.OLLAMA_BASE_URL,
        temperature=config.TEMPERATURE,
        num_predict=1500,
    )


def is_remote() -> bool:
    return config.is_remote()
