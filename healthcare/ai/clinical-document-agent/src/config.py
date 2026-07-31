"""Runtime configuration, loaded from environment (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "meta/llama-3.3-70b-instruct")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MAX_RETRIES = 2
MAX_EDIT_LOOPS = 2
MIN_CONFIDENCE = 0.7
