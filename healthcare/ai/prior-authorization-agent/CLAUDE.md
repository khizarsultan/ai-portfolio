# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. It is scoped to the **Prior Authorization Agent**. See the repo-root `CLAUDE.md` for
monorepo-wide conventions (two-track demo model, Vercel site, ML projects).

## What it is

A LangGraph multi-agent system that runs a medical prior-authorization end to end on synthetic
data: decide if PA is needed → verify coverage → assemble packet → submit to a mock payer →
auto-appeal denials, with a human as the only final gate. The live site demo
(`site/api/pa-agent.py`) is a slimmed replay port — the real system lives here.

## Control flow — the graph is the spec

`src/graph.py` is a real LangGraph `StateGraph`. Nodes are agents; conditional edges branch on
results. The flow (also in the module docstring):

```
intake (consent gate) -> Checker --no PA--> END (auto-clear)
                \--PA--> Verifier --not covered--> END (human review)
                              \--covered--> Assembler -> Submitter --APPROVED--> END
                                                                   --NEEDS_INFO--> Assembler [<=2]
                                                                   --DENIED-----> Appealer -> Submitter [<=2]
```

Load-bearing facts when editing:

- **`_wrap()` wraps every agent node**: it increments `attempt`, runs the agent, then calls
  `contracts.validate_handoff(state)`. A contract violation sets `status="human_review"` and ends
  the run rather than propagating bad state. New nodes should go through `_wrap`.
- **Branch functions are pure** (`after_checker`, `after_submitter`, …) — they read state and
  return the next node name or `END`. Change routing here, not inside agents.
- **Loop caps** (`MAX_NEEDS_INFO_LOOPS`, `MAX_APPEAL_LOOPS` = 2 in `src/config.py`) plus a
  LangGraph `recursion_limit=50` prevent runaway retries. The needs-info/appeal counters live in
  state (`needs_info_loops`, `appeal_loops`).
- **Entry point:** `run_case(case, actor_role, expected_label)` — enforces RBAC (`access.enforce`),
  builds the graph, invokes it inside an `obs.trace_case` context (one Langfuse trace per case).

`src/state.py` — `PAState` is a `TypedDict(total=False)`; every node reads/updates it and appends
to the append-only `audit_log` via `log()`. `status` is `running | done | human_review`.

## The non-negotiable safety invariants

Do not weaken these — they are the entire point of the project:

- **The LLM never decides.** The Checker asks the model to reason but then **defers to the payer
  rule table** on disagreement (`src/agents/checker.py`: `state["needs_pa"] = table_says`). The
  approve/deny call is made by `src/payer/` (rules engine + mock payer), never the model.
- **Every denial/escalation requires a human.** No autonomous denial. Terminal `human_review`
  status is correct behavior, not a bug.
- **Redact before egress.** When the backend is remote (`config.is_remote()` — true for NVIDIA
  NIM), only a Safe-Harbor-redacted case view leaves the machine (`src/compliance/redact.py`).
  Local Ollama sends nothing off-machine.
- **Least-privilege per agent.** `src/governance/identity.py` gives each agent an allow-list of
  tools + `PatientCase` fields, enforced at call time via `src/compliance/access.py` (e.g. the
  Appealer must NOT be able to call `payer.decide`; the Checker can't read clinical notes). Agents
  call `access.enforce_tool(agent, tool)` before acting.

## LLM plumbing

- **Backend swap is one place:** `src/llm/client.py` (`get_llm()`), chosen via `.env`:
  `LLM_BACKEND=nvidia` (hosted, default) or `ollama` (local). `TEMPERATURE=0.0` for repeatable
  evals. Config in `src/config.py`.
- **All structured output goes through `src/llm/structured.py::extract(schema, prompt)`** — a
  Pydantic-validated call with reject-and-retry (`LLM_MAX_RETRIES`, default 2) that raises
  `StructuredError` on exhaustion; agents turn that into a human escalation, never a guess. It
  also tracks `STATS.first_try_rate` for the reliability metric. Use it for any new LLM call.
- **Hallucination guard:** `src/governance/guards.py` drops ICD-10/CPT codes that don't exist in
  the allow-list.

## Commands

```bash
python3.11 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # LLM_BACKEND=nvidia + NVIDIA_API_KEY, or LLM_BACKEND=ollama

# Data: Synthea (see src/data_prep/run_synthea.md) then:
./.venv/bin/python -m src.data_prep.extract_cases            # -> data/processed/case_XXX.json

# Run one case (prints audit trail, decision, plain-English rationale, appeal letter):
./.venv/bin/python -m src.main --case data/processed/case_001.json --role clinician

# Eval vs single-prompt baseline + fairness:
./.venv/bin/python -m eval.build_test_cases                  # -> eval/test_cases.json (~30)
./.venv/bin/python -m eval.run_eval
./.venv/bin/python -m eval.bias_eval                         # approval-rate parity by age/sex

# Tests (pyproject sets testpaths=tests, pythonpath="."):
./.venv/bin/pytest -q                                        # offline (fake LLM)
RUN_LLM_TESTS=1 ./.venv/bin/pytest -q                        # + live-agent tests (needs Ollama)
./.venv/bin/pytest tests/test_graph.py::test_name -q         # single test

# Optional runtime + console:
./.venv/bin/uvicorn src.api:app --port 8000                  # FastAPI; RBAC via X-Role header
cd web && npm install && npm run dev                         # React+Vite provider console :5173
```

## Observability (optional, feature-flagged)

Langfuse is the single tracing/eval layer, gated by `LANGFUSE_ENABLED` (off = safe no-op that
never touches the pipeline). Self-host stack in `deploy/langfuse/docker-compose.yml`. PII masking
runs at both SDK and OTEL-span export stages so no HIPAA identifier reaches a trace. Eval-as-code:
`eval/langfuse_eval.py --upload | --run <name>`.

## Layout

`src/agents/` (checker, verifier, assembler, submitter, appealer) · `src/payer/` (rules_engine +
mock_payer — the deterministic decision) · `src/governance/` (contracts, guards, identity,
explain) · `src/compliance/` (redact, audit, access, consent) · `src/llm/` (client, structured) ·
`eval/` · `tests/` · `web/` (React console) · `plan*.md` (design history). `data/`, `.venv/`,
traces are gitignored.
