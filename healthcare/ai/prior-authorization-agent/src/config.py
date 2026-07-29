"""Central config. Model name and paths live here, never hardcoded in agents."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROCESSED = DATA / "processed"          # flagged "encrypted-at-rest in prod" (see README)
SYNTHEA_OUT = DATA / "synthea_output"
RULES_DIR = DATA / "payer_rules"

# LLM backend: "nvidia" = NVIDIA NIM hosted open-weight models (build.nvidia.com, free tier,
# OpenAI-compatible); "ollama" = fully local (zero egress). Swap in one place via .env.
LLM_BACKEND = os.getenv("LLM_BACKEND", "nvidia")
REMOTE_BACKENDS = {"nvidia"}          # backends where data leaves the machine -> redact first

# NVIDIA NIM (hosted). Free key from build.nvidia.com looks like nvapi-...
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Ollama (local fallback).
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Active model id. NIM default supports structured output; for Ollama use e.g. qwen3:14b.
_DEFAULT_MODEL = "meta/llama-3.3-70b-instruct" if LLM_BACKEND == "nvidia" else "qwen3:14b"
MODEL_NAME = os.getenv("MODEL_NAME", _DEFAULT_MODEL)


def is_remote() -> bool:
    """True when the active backend sends data off-machine (redact PHI-style fields first)."""
    return LLM_BACKEND in REMOTE_BACKENDS

# Reliability: reject + retry invalid structured output before escalating (planv2 B1/B3.2).
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
TEMPERATURE = 0.0                        # deterministic reasoning for repeatable evals

# Loop safety caps (plan §3).
MAX_NEEDS_INFO_LOOPS = 2
MAX_APPEAL_LOOPS = 2

# GDPR retention policy (planv2 B2). Illustrative — see README.
RETENTION_DAYS = 365

# Observability (planv4 D): Langfuse tracing + evals. Feature-flagged so it can be turned off
# and never breaks the PA pipeline when absent. Self-hosted default (docker at :3000).
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_PROJECT_ID = os.getenv("LANGFUSE_PROJECT_ID")   # optional, enables exact deep-links

# Illustrative NIM token pricing (USD per 1M tokens) so Langfuse can compute cost. The free
# tier is $0; these are stand-in list prices for the cost dashboard.
MODEL_PRICING = {
    "meta/llama-3.1-8b-instruct": {"input": 0.05, "output": 0.05},
    "meta/llama-3.3-70b-instruct": {"input": 0.60, "output": 0.60},
}
