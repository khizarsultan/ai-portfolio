# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A monorepo portfolio of AI/ML projects across three domains (`healthcare/`, `cybersecurity/`,
`finance/`), plus a Next.js site (`site/`) that presents them with **live, in-browser demos**.
Everything runs on **synthetic or public data** — no real PHI. The two flagship pieces are the
LangGraph multi-agent systems under `healthcare/ai/`.

## The two-track demo architecture (read this first)

Each project exists in **two forms**, and the split is the most important thing to understand:

1. **Full standalone project** in a domain folder — the real thing, with training, MLOps, a
   Streamlit dashboard (ML) or a CLI + FastAPI + React console (agents). Heavy deps (sklearn,
   shap, langgraph, an LLM). Not deployed to the public site.
2. **Slimmed self-contained port** inside `site/` — what actually ships to Vercel and is always
   online. It must be lightweight and self-contained (no cross-module imports at runtime).

Two bridges connect track 1 → track 2, and edits often need to touch both sides:

- **ML projects** → `precompute_demo.py` (in each `ml/*` project root) runs the real artifact +
  MLflow registry offline and writes numbers to `site/public/demo-data/<name>.json`. The site
  ships *numbers*, never sklearn/shap/plotly/mlflow. The interactive ML demos that take live user
  input are Python serverless functions in `site/api/*.py` that load a **slimmed** `.joblib`
  (model + preprocessor only) from `site/api/models/`.
- **Agent projects** → ported into a single self-contained `site/api/pa-agent.py` /
  `site/api/clinical-doc.py`, bounded to a handful of prerecorded/synthetic cases (PA replays
  `site/api/pa_samples.json` when no API key is set).

`site/lib/projects.ts` is the **single source of truth** for the project catalog. A demo link
resolves to an internal `demoPath` first, else an external `NEXT_PUBLIC_DEMO_*` env URL, else the
card shows "Demo coming soon" (so the site is always shippable).

## site/ — Next.js 15 + React 19 + Tailwind 3 (deployed on Vercel)

```
site/
  app/            App Router: home, projects/[slug], demos/<name> (one page per demo)
  api/*.py        Vercel Python serverless functions — the live demo backends
  api/models/     Slimmed .joblib artifacts that ship with the deploy
  components/     UI; components/demo/ holds the interactive demo widgets + flow graphs
  lib/projects.ts Project catalog + demo-URL resolution (single source of truth)
  scripts/dev_api.py  Local shim that runs api/*.py (see gotcha below)
```

Commands (run from `site/`):
```bash
npm install
npm run dev          # Next.js frontend at http://localhost:3000
npm run build        # production build (also the Vercel buildCommand)
npm run lint         # next lint
```

**Gotcha — `next dev` does NOT run the `api/*.py` functions.** Only `vercel dev` or a real deploy
execute them. For local Python-backed demos, run the shim in a second terminal:
```bash
python3 scripts/dev_api.py      # serves api/*.py on :8787
```
`next.config.mjs` rewrites `/api/*` → `127.0.0.1:8787` in dev only (returns `[]` in production).

**Gotcha — pinned runtime deps.** `site/requirements.txt` pins exact
scikit-learn/numpy/pandas/scipy versions because the `.joblib` models must unpickle against the
same versions they were trained with. Do not bump these casually. `site/vercel.json` bundles
`api/models/**` into each ML function and gives the agent functions more memory/duration.

The `api/*.py` functions are plain stdlib `BaseHTTPRequestHandler` classes (no framework) exposing
`GET` (metadata/fields/defaults) and `POST` (prediction). Feature engineering is **inlined** to
match training exactly and keep the function self-contained.

## healthcare/ai/ — LangGraph multi-agent systems (the flagships)

`prior-authorization-agent/` and `clinical-document-agent/` are full Python packages
(`src/`, `eval/`, `tests/`; PA also has a `web/` React+Vite provider console). Same architecture:

- **Orchestration:** LangGraph state machine (`src/graph.py`) wiring ~5 single-job agents
  (`src/agents/`) with conditional edges and **loop caps** so it can't retry forever. State +
  append-only audit trail travel together in one Pydantic `HandoffContext`, validated at every
  edge; a contract violation escalates to human review rather than propagating bad state.
- **Decisions are deterministic, not the LLM.** The LLM only reads/reasons/drafts. The PA
  approve/deny call is made by a rules engine + mock payer (`src/payer/`); clinical codes are
  validated against real ICD-10/CPT sets and invented codes are dropped by a guard. Every
  denial/escalation requires human sign-off — no autonomous denial or record write.
- **LLM backend is swappable in one place** (`src/llm/client.py`), chosen entirely via `.env`:
  NVIDIA NIM (hosted, default) or local Ollama (zero egress). With the hosted backend, only a
  HIPAA Safe-Harbor **redacted** view leaves the machine (`src/compliance/redact.py`).
- **Governance** lives in `src/governance/` (versioned contracts, hallucination guards,
  per-agent least-privilege identities, bias/explainability). **Observability** is Langfuse,
  feature-flagged via `LANGFUSE_ENABLED` (off is a safe no-op).

Commands (from the project dir, e.g. `healthcare/ai/prior-authorization-agent/`):
```bash
python3.11 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cp .env.example .env                                    # set NVIDIA_API_KEY or use Ollama

./.venv/bin/python -m src.main --case data/processed/case_001.json --role clinician   # PA: one case
# clinical-doc uses: python -m src.main --case data/processed/enc_001.json --signoff sign|edit|reject

./.venv/bin/python -m eval.run_eval        # agent system vs single-prompt baseline
./.venv/bin/python -m eval.bias_eval       # approval-rate parity across slices (PA)

./.venv/bin/pytest -q                      # offline tests (fake LLM) — payer/compliance/governance/graph
RUN_LLM_TESTS=1 ./.venv/bin/pytest -q      # also live-agent tests (needs Ollama serving)
```
Run a single test: `./.venv/bin/pytest tests/test_graph.py::test_name -q`. pytest config
(`testpaths`, `pythonpath`) is in each `pyproject.toml`.

PA optional runtime: `./.venv/bin/uvicorn src.api:app --port 8000` (FastAPI, RBAC via `X-Role`)
plus `cd web && npm install && npm run dev` for the React console at :5173.

## ml/ projects (cybersecurity, finance) — identical shape

`cybersecurity/ml/{malicious-url-detection,sms-spam-detection}`, `finance/ml/credit-card-fraud`.
Each has (sms-spam is the minimal case — `app/` only):

- `app/` — **Streamlit** dashboard: `app.py` (presentation) + `core.py` (UI-agnostic
  metrics/SHAP/benchmark/PSI) + `features.py` (engineering shared by train & live input) +
  `train.py` (builds `artifact.joblib`) + `Dockerfile`. The dashboard needs only the artifact at
  runtime; the raw CSV is never shipped.
  ```bash
  cd <project>/app && pip install -r requirements.txt && streamlit run app.py   # :8501
  ```
- `mlops/` — a champion/challenger pipeline CLI (`pipeline.py`) over an MLflow registry, with
  drift-triggered retrain + a manual promotion gate. Stages are subcommands:
  ```bash
  cd <project>/mlops
  python pipeline.py bootstrap                 # train champion on reference split
  python pipeline.py run --drift               # make-window → check-drift → (retrain+evaluate)
  python pipeline.py promote --approve --by me # manual gate; --reject to decline
  python pipeline.py status
  ```
- `notebooks/` — EDA + modeling; `precompute_demo.py` — emits the site JSON (see two-track above).

## Data & artifacts (gitignored)

`data/`, `*.csv`, `mlruns/`, and `*.joblib`/`*.pkl` are gitignored — datasets come from Kaggle
via `kagglehub` (see `ml-projects.md` for slugs/paths) and models are regenerable. The **one
exception** is `site/api/models/*.joblib` (small, data-free) which is force-un-ignored because it
must ship to Vercel. Secrets: everything `.env*` is ignored except `.env.example`.
