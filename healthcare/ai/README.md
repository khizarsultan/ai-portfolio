# Prior Authorization Agent

A multi-agent system that handles a medical **prior authorization (PA)** request end to end:
decide if PA is needed, verify coverage, assemble the request, submit it to a (mock) payer,
and automatically appeal denials — with a human doing final review only.

Built by **Khizar Sultan** as an agentic-AI portfolio piece. Runs on **synthetic data** with an
**open-weight LLM** — no real patients, no real insurer, no PHI. Two interchangeable backends:
**NVIDIA NIM** (hosted free tier, default) with Safe-Harbor **redaction before any egress**, or
**local Ollama** (zero egress, no API key) — swap in one line.

## Why agents (the pitch)
A single prompt fumbles the multi-step cases — needs-info loops and deny-then-appeal.
A **team of small agents**, each with one job, handles the branching and recovers denials,
while every step is written to an append-only **audit trail** — the selling point for a
healthcare workflow.

## The team
| Agent | Job | Backed by |
|-------|-----|-----------|
| **Checker** | Does this order need PA under the plan? | LLM + rule table |
| **Verifier** | Is coverage active and the procedure covered? | Mock payer eligibility |
| **Assembler** | Build a complete, truthful PA packet from the record | LLM |
| **Submitter** | Send the packet to the payer, read the decision | Mock payer |
| **Appealer** | On denial, find evidence and draft an appeal | LLM |

An **orchestrator** (LangGraph) wires them with conditional edges and loop caps (max 2
needs-info, max 2 appeals) so it can't retry forever.

```
intake (consent gate) -> Checker --no PA--> done (auto-clear)
                \--PA--> Verifier --not covered--> human review
                               \--covered--> Assembler -> Submitter --APPROVED--> done
                                                                    --NEEDS_INFO--> Assembler [<=2]
                                                                    --DENIED-----> Appealer -> Submitter [<=2]
```

## Stack
LangGraph · LangChain · **open-weight LLM — NVIDIA NIM (hosted, default) or Ollama (local)** ·
Pydantic v2 · Synthea (synthetic FHIR patients) · deterministic mock payer · FastAPI · pytest.

## Setup
```bash
cd healthcare/ai
python3.11 -m venv .venv          # already created
./.venv/bin/pip install -e ".[dev]"
cp .env.example .env

# Backend A (default): NVIDIA NIM — free hosted open-weight models
#   get a free key at https://build.nvidia.com (looks like nvapi-...), then in .env:
#   LLM_BACKEND=nvidia   NVIDIA_API_KEY=nvapi-...   MODEL_NAME=meta/llama-3.3-70b-instruct

# Backend B: local Ollama — zero egress, no API key
#   in .env: LLM_BACKEND=ollama   MODEL_NAME=qwen3:14b
brew install ollama && ollama serve & ollama pull qwen3:14b   # ~9GB, one time
```
Backend + model are chosen entirely in `.env`; `src/llm/client.py` is the **single swap point**.
When the backend is remote (NIM), agents send a **de-identified** case view (`compliance.redact`);
the local backend sends the full record because nothing leaves the machine.

## Data
Synthea generates synthetic FHIR patients (`src/data_prep/run_synthea.md`), then:
```bash
./.venv/bin/python -m src.data_prep.extract_cases   # -> data/processed/case_XXX.json
```
Synthea supplies realistic demographics/history; `extract_cases.py` maps each patient onto one
of five PA-relevant procedures and derives the PA coding (documented in the script). The
**labeled eval set** is authored separately (`eval/build_test_cases.py`) so metrics are repeatable.

## Run one case
```bash
./.venv/bin/python -m src.main --case data/processed/case_001.json --role clinician
```
Prints the audit trail, the decision, a **plain-English rationale**, and any appeal letter.

## Evaluate (agents vs single-prompt baseline)
```bash
./.venv/bin/python -m eval.build_test_cases     # writes eval/test_cases.json (~30 cases)
./.venv/bin/python -m eval.run_eval             # accuracy + governance metrics vs baseline
./.venv/bin/python -m eval.bias_eval            # approval-rate parity across age/sex slices
```
Reports PA-needed accuracy, final-decision accuracy (agent vs baseline), appeal-recovery rate,
avg steps, audit completeness, **schema first-try pass rate, hallucinated-code rate,
transparency (% with rationale)**, and **fairness** (approval-rate parity).

## Observability & evals (Langfuse — Phase 8)
Langfuse is the single tracing + eval layer (planv4 D): every case = one trace/session, every
agent = a span, every LLM/tool call = a nested observation with tokens, latency, cost, errors,
and full per-step reasoning. Custom scores (`decision_correct`, `schema_first_try`,
`hallucination_flag`, `escalated`, `approved`) and demographic tags (age band, sex) feed the
accuracy / fairness / reliability / cost dashboards. Feature-flagged (`LANGFUSE_ENABLED`) — off
is a safe no-op that never affects the pipeline.
```bash
# Self-host (docker) — Postgres + ClickHouse + Redis + MinIO + Langfuse web/worker
cd deploy/langfuse && docker-compose up -d          # UI at http://localhost:3000
# keys auto-provisioned via deploy/langfuse/.env (LANGFUSE_INIT_*); copy them into ../../.env:
#   LANGFUSE_ENABLED=true  LANGFUSE_HOST=http://localhost:3000
#   LANGFUSE_PUBLIC_KEY=pk-lf-...  LANGFUSE_SECRET_KEY=sk-lf-...  LANGFUSE_PROJECT_ID=pa-demo
```
```bash
./.venv/bin/python -m eval.langfuse_eval --upload            # test_cases.json -> Langfuse dataset
./.venv/bin/python -m eval.langfuse_eval --run baseline-v1   # run agents as a Langfuse experiment
```
Each PA case run (CLI, API, or console **Run agent flow**) is traced automatically. The console's
**View full trace ↗** link deep-links to the case's Langfuse session. **PII masking (D6)** is on:
a Safe-Harbor scrubber runs at both the SDK and OTEL-span export stages, so no HIPAA identifier
reaches a trace (verified: SSN/phone → `[SSN]`/`[PHONE]`). Data here is synthetic; for real PHI
you would **self-host** Langfuse so trace data stays in your own infra (the docker stack above).

## Tests
```bash
./.venv/bin/pytest -q                 # payer/compliance/governance/graph-structure run offline
RUN_LLM_TESTS=1 ./.venv/bin/pytest -q # also runs live-agent tests (needs Ollama serving)
```

## Demo API (optional)
```bash
./.venv/bin/uvicorn src.api:app --reload
# POST /submit  (X-Role header sets RBAC role; full packet only for reviewer/admin)
# DELETE /case/{id}  (right to erasure; reviewer/admin only)
```

## Provider console (frontend — Phase 7)
An internal PA-team console (React + Vite + Tailwind, React Query) over the FastAPI backend:
**Queue** (filter/search, status badges, turnaround), **Case detail** (patient/order summary,
pipeline stepper, decision + plain-English rationale, role-gated Approve / Send back / Escalate),
and a **Review** view filtered to `human_review` with the escalation reason inline.
```bash
./.venv/bin/uvicorn src.api:app --port 8000   # terminal 1: backend
cd web && npm install && npm run dev           # terminal 2: console at http://localhost:5173
```
Console endpoints: `GET /cases?status=&q=`, `GET /cases/{id}`, `POST /cases/{id}/{run|approve|send-back|escalate}`.
The store is seeded from the labeled eval set (`eval/test_cases.json`); a case starts at
`needs_pa`, **Run agent flow** executes the pipeline, and reviewer actions require the
`reviewer`/`admin` role (top-right role switch). Deferred (planv3 C6): eval dashboards, deep
per-step reasoning views, audit-trail explorer, real auth/SSO.
In production this would run over **HTTPS** (encryption in transit) and the processed-case
store would be **encrypted at rest** — the `data/processed/` folder stands in for that.

---

## Compliance & data protection (HIPAA / GDPR patterns)
Synthetic data is treated **as if it were real PHI**. This is not "certified compliant" — it
demonstrates the controls a real system needs (`src/compliance/`):

- **De-identification / minimization** — `redact.py` strips the 18 HIPAA Safe Harbor
  identifiers from anything logged; each agent receives only the fields its job needs.
- **Audit logging** — `audit.py`: append-only, timestamped who/what/when; never mutable.
- **Access control (RBAC)** — `access.py`: clinician / reviewer / admin; only reviewer/admin
  may approve, view full packets, or erase.
- **GDPR purpose limitation** — `consent.py`: every case must carry a `purpose` + `lawful_basis`
  or processing is refused at intake.
- **Retention + erasure** — `delete_case()` and `DELETE /case/{id}`; documented retention policy.
- **Encryption** — noted where at-rest/in-transit encryption applies (DB, API).
- **Egress control** — with the hosted NIM backend, only a **Safe-Harbor-redacted** view of the
  case is sent off-machine (`redact.case_payload`); clinical codes are kept, identifiers are not.
- **Local model = no BAA** — switching to the local Ollama backend means no data leaves the
  machine at all (zero third-party disclosure) — the cleanest compliance posture, one `.env` flag away.

## Agent governance (the four pillars — `src/governance/`)
1. **Interoperability** — agents hand off via a **versioned Pydantic contract**
   (`contracts.py`, `HandoffContext`), validated at every edge; FHIR is the input interchange
   format; handoffs are idempotent (safe under retries).
2. **Trust, safety & reliability** — every LLM output is schema-validated with reject-and-retry
   (max 2) then escalates; a **hallucination guard** (`guards.py`) drops ICD-10/CPT codes that
   don't exist; **the mock payer, not the LLM, makes the decision**; loop caps prevent runaway.
3. **Privacy, identity & access** — each agent has a **scoped identity** (`identity.py`) with a
   least-privilege allow-list of tools/fields, policy-checked at call time (e.g. the Appealer
   cannot call the payer's decision path; the Checker can't read clinical notes).
4. **Ethics, bias & transparency** — `bias_eval.py` measures approval-rate parity across
   age/sex; **all denials/escalations require human review (no autonomous denial)**; every
   decision yields a plain-English rationale (`explain.py`); escalations surface `status =
   human_review` with the reason.

### Handoff protocol
State + audit travel together in one `HandoffContext`. Each node: (1) does its scoped work,
(2) appends to the append-only audit trail, (3) returns updated state, which the orchestrator
**validates against the contract** before the next node runs. A contract violation escalates to
human review rather than propagating bad state.

## Model / system card
- **What it does:** automates the PA workflow (need-check → coverage → assemble → submit →
  appeal) on synthetic data, with a human reviewer as the final gate.
- **Model:** open-weight, deterministic (temp 0). Default `meta/llama-3.3-70b-instruct` via
  NVIDIA NIM (hosted, redacted egress); `qwen3:14b` via local Ollama for zero egress. Swappable in `.env`.
- **Data:** Synthea synthetic FHIR (US-based); authored payer rules; no PHI.
- **Decisions:** made by a **deterministic rules engine**, not the LLM. The LLM only reasons,
  extracts, and drafts.
- **Known limits:** small local models can produce invalid JSON (mitigated by retry + escalate);
  the ICD-10/CPT allow-list is an illustrative subset; appeal recovery depends on evidence
  actually being present in the record.
- **Human-in-the-loop:** required for every denial and every escalation. No fully-autonomous denial.

## Out of scope
No real payer APIs, no real EHR, no PHI. Not HIPAA-compliant infrastructure — a demo on
synthetic data. No UI beyond the CLI and optional FastAPI endpoint.
