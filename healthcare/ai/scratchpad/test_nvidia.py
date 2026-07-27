"""Minimal check: is the NVIDIA NIM API reachable and the key valid?

Uses ChatNVIDIA (same client the app uses).

Run:
    cd healthcare/ai
    ./.venv/bin/python scratchpad/test_nvidia.py
"""
import os
import sys

from langchain_nvidia_ai_endpoints import ChatNVIDIA

BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = os.getenv("MODEL_NAME", "meta/llama-3.3-70b-instruct")

# load .env if present (no extra deps)
env = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env):
    for line in open(env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

key = os.getenv("NVIDIA_API_KEY")
if not key:
    sys.exit("NVIDIA_API_KEY not set (check .env)")
print(f"key prefix={key[:5]}... base_url={BASE_URL} model={MODEL}")

llm = ChatNVIDIA(model=MODEL, api_key=key, base_url=BASE_URL,
                 temperature=0.0, max_tokens=10)

try:
    resp = llm.invoke("Reply with exactly: OK")
    print("RESPONSE:", resp.content.strip())
    print("API WORKING")
except Exception as e:
    print("API FAILED")
    print(type(e).__name__, e)
    sys.exit(1)
