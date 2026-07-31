# Clinical Documentation Agent — Implementation Plan

## 1. Goal

Build an agentic system that turns a patient visit input into a finished clinical note:
generate a **SOAP note**, extract **diagnosis/procedure codes**, and update the record —
but only after a **clinician signs off**. This attacks the documentation burden (docs eat
up to ~35% of physician time).

Portfolio project. Runs on **MIMIC** deidentified records (credentialed via PhysioNet), with
a **synthetic/public fallback** for development while credentialing is pending.

Success = given an encounter's raw notes, produce a complete, factually-grounded SOAP note +
accurate ICD-10/CPT codes (scored against MIMIC's real codes), gated by a mandatory clinician
sign-off, with a full audit trail — and beat a single-prompt baseline.

**Hard rule: nothing is written to the patient record without a human sign-off.**

---

## 2. What we're building (plain version)

A team of small agents, each with one job:

- **Intake** — normalize the visit input (transcript or raw notes) into clean encounter text.
- **SOAP Writer** — draft the note: Subjective, Objective, Assessment, Plan.
- **Coder** — extract ICD-10 diagnosis codes + CPT/procedure codes from the note.
- **Validator** — check codes are real, SOAP is complete, and every claim traces back to the
  source; raise flags.
- **Recorder** — write the note to the (mock) EHR — only after the clinician signs off.

An orchestrator wires them together. The LLM drafts; humans approve.

---

## 3. Architecture

Linear-with-gate graph (LangGraph). Nodes = agents.

```
[intake]
  -> SOAP Writer -> Coder -> Validator
       -> flags / low confidence -> [human_review]
       -> otherwise              -> [await sign-off]   (HUMAN-IN-THE-LOOP, required)
                                        -> signed   -> Recorder -> [end: recorded]
                                        -> edited/rejected -> back to SOAP Writer/Coder
                                                              [loop, max 2] then human_review
```

Every node appends to `audit_log`. Nothing reaches the Recorder before sign-off.

**Trust anchor:** unlike a decision system, this is a generation task, so the anchors are
(1) codes validated against **real ICD-10/CPT code sets** (deterministic guard), and
(2) a **mandatory clinician sign-off**. The model never writes to the record on its own.

---

## 4. Tech stack

- **Python 3.11+**, **LangGraph**, **LangChain**, **Pydantic v2**
- **Open-source LLM, free** — NVIDIA NIM (hosted) or Ollama (local); see Part B / §B1
- **MIMIC-III / MIMIC-IV** data (PhysioNet, credentialed) + a synthetic/public dev fallback
- **Mock EHR** — Python module storing signed records (FHIR-shaped)
- **Code sets** — ICD-10-CM + CPT/HCPCS reference lists (for the Validator)
- **FastAPI** (backend for the console), **pytest**, **python-dotenv**

Do NOT use real MIMIC data before PhysioNet credentialing is complete. Nothing writes to the
record without human sign-off.

---

## 5. Repo structure

```
clinical-doc-agent/
├── plan-clinical-documentation.md
├── README.md
├── pyproject.toml
├── .env.example
├── data/
│   ├── mimic/                 # credentialed extract (gitignored)
│   ├── fallback/              # public/synthetic dev notes (mtsamples etc.)
│   ├── code_sets/             # icd10cm.csv, cpt.csv
│   └── processed/             # EncounterCase json
├── src/
│   ├── state.py              # EncounterState
│   ├── models.py             # Pydantic: EncounterCase, SOAPNote, CodeSet, Record
│   ├── graph.py              # LangGraph + sign-off gate
│   ├── agents/
│   │   ├── intake.py
│   │   ├── soap_writer.py
│   │   ├── coder.py
│   │   ├── validator.py
│   │   └── recorder.py
│   ├── ehr/
│   │   └── mock_ehr.py        # write signed record (FHIR-shaped), read
│   ├── codes/
│   │   └── code_lookup.py     # load + validate ICD-10 / CPT codes
│   ├── llm/                   # see Part B
│   ├── compliance/            # see Part B
│   ├── governance/            # see Part B
│   ├── data_prep/
│   │   ├── mimic_access.md    # how to get credentialed + which tables
│   │   └── extract_cases.py   # -> EncounterCase json
│   └── main.py               # run one encounter (CLI)
├── eval/
│   ├── test_cases.json
│   ├── baseline.py
│   ├── run_eval.py
│   └── bias_eval.py
└── tests/
    ├── test_agents.py
    ├── test_codes.py
    └── test_graph.py
```

---

## 6. Data setup

### MIMIC (primary, credentialed)
- Access needs **PhysioNet credentialing**: CITI "Data or Specimens Only Research" training +
  a signed Data Use Agreement. This takes time — start it first.
- **Prefer MIMIC-IV** (has ICD-10 codes) + the **MIMIC-IV-Note** module (discharge summaries,
  radiology notes) for free-text input. MIMIC-III `NOTEEVENTS` is ICD-9 — usable but older.
- Input = free-text notes. **Ground-truth codes** for eval = `diagnoses_icd` / `procedures_icd`
  linked to each admission (mind `icd_version`).
- `extract_cases.py` -> `EncounterCase` json: encounter_id, demographics (age band, sex),
  source note text, reference codes.

### Dev fallback (while credentialing pending)
- Use a **public medical transcription dataset (e.g. mtsamples)** or LLM-generated synthetic
  notes to build against. Same `EncounterCase` shape, so switching to MIMIC later is a data
  swap, not a code change.

### Code sets
- Load ICD-10-CM and CPT/HCPCS reference lists into `data/code_sets/` for the Validator's
  code-existence check.

---

## 7. Component specs

### State (`state.py`)
```python
class EncounterState(TypedDict):
    case: EncounterCase
    encounter_text: str | None      # cleaned input
    soap: SOAPNote | None           # S / O / A / P
    codes: list[Code] | None        # icd10 + cpt with rationale
    flags: list[str]                # validation issues
    confidence: float | None
    signed_off: bool
    signer: str | None
    attempt: int
    audit_log: list[str]
    status: str                     # running | await_signoff | recorded | human_review
```

### Intake (`agents/intake.py`)
- **In:** raw visit input (notes/transcript). **Job:** clean + structure into `encounter_text`.
- **Out:** `encounter_text` + audit entry.

### SOAP Writer (`agents/soap_writer.py`)
- **In:** `encounter_text` (+ edit feedback on a loop). **Job:** draft `SOAPNote` (4 sections),
  each claim grounded in the source. **Out:** `SOAPNote` + audit entry.

### Coder (`agents/coder.py`)
- **In:** `SOAPNote` + `encounter_text`. **Job:** extract ICD-10 + CPT codes, each with a short
  rationale (why this code). **Out:** `list[Code]` + audit entry.

### Validator (`agents/validator.py`)
- **In:** `SOAPNote` + `codes`. **Job (deterministic + LLM):** codes exist in the real code
  sets (`code_lookup`); all 4 SOAP sections present; claims trace to source (grounding check);
  set `confidence` and `flags`. **Out:** flags/confidence + audit entry.

### Recorder (`agents/recorder.py`)
- **In:** signed `SOAPNote` + `codes`. **Job:** write to `mock_ehr` as a FHIR-shaped record —
  **only if `signed_off` is true**. **Out:** record id + audit entry.

---

## 8. Implementation phases

**Phase 1 — Data foundation**
- Repo, config, README skeleton; start PhysioNet credentialing.
- Wire the dev fallback dataset; load ICD-10/CPT code sets.
- `extract_cases.py` -> `EncounterCase` json (fallback now, MIMIC when granted).
- ✅ Deliverable: processed cases + code sets + a test.

**Phase 2 — Code lookup + validator guard**
- `code_lookup.py` (load + validate codes); Validator's deterministic checks.
- ✅ Deliverable: passing `tests/test_codes.py`.

**Phase 3 — Agents (no graph)**
- Implement all 5 agents standalone; test each on a fixed encounter.
- ✅ Deliverable: passing `tests/test_agents.py`.

**Phase 4 — Graph + sign-off gate**
- Wire the graph from §3, including the mandatory `await_signoff` gate and loop caps.
- `main.py`: run one encounter, print SOAP + codes + status.
- ✅ Deliverable: full flow stops at sign-off; Recorder only writes after sign-off.

**Phase 5 — Eval + baseline**
- Build `eval/test_cases.json`; `baseline.py` (single prompt: note in -> SOAP+codes out).
- `run_eval.py`: metrics vs baseline (see §10).
- ✅ Deliverable: eval report; agents beat baseline on coding + grounding.

(Then Part B/C/D phases: governance, console, observability.)

---

## 9. (see §10)

## 10. Evaluation metrics

Run on `eval/test_cases.json`:
- **SOAP completeness** — all four sections present and non-trivial.
- **Factual grounding / hallucination rate** — % of SOAP claims supported by the source note
  (LLM-as-judge or NLI check). Lower is better.
- **Coding accuracy** — precision / recall / F1 of extracted ICD-10/CPT vs **MIMIC's real
  codes** (this is genuine ground truth — the selling point of using MIMIC).
- **Reliability** — schema-valid-on-first-try rate; code-existence pass rate.
- **Fairness** — coding F1 + grounding across age/sex slices.
- **Cost** — cost per note.

Compare against the single-prompt baseline. Story: the agent system produces better-grounded
notes and more accurate codes, with a sign-off gate a single prompt can't provide.

---

## 11. Out of scope (state in README)

- No audio/ASR — assume text input (transcript already produced).
- No real EHR integration; mock only.
- No real PHI before PhysioNet credentialing; not certified HIPAA-compliant infra.
- No UI beyond the console (Part C) + CLI.

---

## 12. Getting started

```bash
cp .env.example .env
pip install -e .
python -m src.data_prep.extract_cases        # fallback data first
python -m src.main --case data/processed/enc_001.json
python -m eval.run_eval
```

---

# Part B — LLM + compliance + governance

Same cross-cutting requirements as the prior-auth project, adapted here.

## B1. LLM setup — free, no Claude keys

Both options are free and OpenAI-compatible. Build one `get_llm()` factory in
`src/llm/client.py`; all agents import from it, so switching providers is one config line.

- **Option A (primary): NVIDIA NIM** — hosted, free. Sign up at build.nvidia.com (Developer
  Program, no card; ~1,000 free credits, up to 5,000; some models free; 40 req/min). OpenAI-
  compatible base URL `https://integrate.api.nvidia.com/v1`; use `ChatOpenAI` pointed there.
  Your Mac's RAM is not a limit, so you can use a stronger model (e.g. Llama-70B, Qwen, GLM).
- **Option B (fallback): Ollama** — local/private. `brew install ollama`, `ollama pull qwen3:8b`,
  `ollama serve`; `ChatOllama` at `http://localhost:11434`. 16 GB -> `qwen3:8b`; 24 GB+ -> `qwen3:14b`.

`.env`:
```
LLM_PROVIDER=nvidia            # nvidia | ollama
NVIDIA_API_KEY=...
MODEL_NAME=meta/llama-3.1-70b-instruct
OLLAMA_BASE_URL=http://localhost:11434
```

**Reliability note:** open models are weaker at strict JSON. So keep the anchors deterministic
(code validation) and human (sign-off) — the LLM only drafts/extracts. Use
`.with_structured_output(...)` or JSON + Pydantic validation; reject + retry (max 2) on bad output.

**Compliance trade-off:** hosted NIM means data leaves your machine — fine here because data is
deidentified/synthetic, but note that real PHI would need a BAA or self-hosting; the local
(Ollama) path discloses nothing. Document which you run.

New files:
```
src/llm/
├── client.py          # get_llm() factory (nvidia | ollama)
└── structured.py       # prompt -> validated Pydantic (retry on bad JSON)
```

## B2. Compliance & data protection (HIPAA / GDPR patterns)

We use deidentified/synthetic data — this demonstrates the controls, not certification. Treat
data as if it were PHI. Implement a thin `src/compliance/`:

- **De-identification / minimization** — `redact.py` strips the 18 HIPAA Safe Harbor identifiers
  from logs and any hosted-model prompt; each agent gets only the fields it needs.
- **MIMIC DUA rules** — the PhysioNet DUA forbids attempts to **re-identify** patients and
  forbids redistributing the data. Enforce in code/README: no re-identification, data stays
  in `data/mimic/` (gitignored), never committed.
- **Audit logging** — `audit.py`: append-only, timestamped who/what/when for every action and
  data access (extends the existing `audit_log`).
- **Access control (RBAC)** — `access.py`: roles `clinician`, `coder`, `admin`. Only a
  `clinician` can sign off; only signed notes reach the Recorder.
- **GDPR: purpose + erasure** — `consent.py`: `purpose` / `lawful_basis` tags per encounter;
  `delete_record(id)` + documented retention.
- **LLM data-flow posture** — document hosted-vs-local trade-off (see B1) in the model card.

New files:
```
src/compliance/
├── redact.py
├── access.py
├── consent.py
└── audit.py
```

## B3. Agent governance (four pillars)

### B3.1 Interoperability
- Agents exchange **versioned Pydantic contracts**, not loose dicts; validate every handoff.
- Output the finished note as **FHIR** (`DocumentReference`/`Composition` for the note;
  `Condition`/`Procedure` for codes) so the record speaks a real standard.
- A single `HandoffContext` carries state + audit trail; handoffs idempotent under retries.

### B3.2 Trust, safety & reliability
- Validate every agent output against its contract; reject + retry (max 2) then escalate.
- **Hallucination guards:** (a) code-existence check against real ICD-10/CPT sets; (b) SOAP
  claims must trace to the source note (grounding check) — unsupported claims get flagged.
- **Mandatory human sign-off** before any record write (the core safety property).
- Loop caps + circuit breaker; eval harness + regression tests on every change.

### B3.3 Privacy, identity & access
- Each agent has a **scoped identity + least-privilege permissions** (`AgentIdentity`):
  only the **Recorder** can write to the EHR, and only when `signed_off`; the Coder/Writer
  cannot write; agents get only the data fields their job needs.
- Tool/data access is policy-checked at call time (`compliance/access.py`).

### B3.4 Ethics, bias & transparency
- **Bias eval** — coding accuracy + grounding across age/sex slices; report disparities.
- **Human-in-the-loop** — sign-off is required; no autonomous record write.
- **Transparency** — each code carries a plain-English rationale; each note has a readable
  summary of what the agents did (`explain.py` over the audit trail).
- **Escalation** — clear `human_review` route with reasons attached.
- Ship a **model/system card** in the README (what it does, data, limits, human gates).

New files:
```
src/governance/
├── contracts.py        # versioned handoff schemas + FHIR output
├── identity.py         # AgentIdentity + per-agent permission scopes
├── guards.py           # code-existence + grounding checks
└── explain.py          # audit trail -> human-readable rationale
eval/bias_eval.py        # accuracy/grounding parity across slices
```

## B4. Extra phase
**Phase 6 — Governance & compliance layer** (after Phase 5): build `src/compliance/` and
`src/governance/`, add `bias_eval.py`, update README with model card + DUA/compliance notes.
✅ Deliverable: every note has rationale + audit trail; bias report; per-agent permissions
enforced; only Recorder writes, only after sign-off; PHI-style fields redacted from logs.

## B5. Extra eval metrics (add to §10)
- Fairness (coding F1 / grounding parity across slices), reliability (schema-valid %,
  hallucinated-code %, grounding %), transparency (% notes with complete rationale),
  access enforcement (tests proving only Recorder writes, only after sign-off).

---

# Part C — Frontend (clinician console)

Internal **provider-side console** — for the care team, not patients. Build the working app.

## C1. Users / roles
- **Clinician** — primary; reviews the draft and **signs off** (the required gate).
- **Coder / billing** — reviews and adjusts extracted codes.
- **Admin** — oversight, escalations.
Simple role switch for now — no full auth yet.

## C2. Stack
React + Vite + Tailwind -> existing FastAPI backend; React Query for fetches.
Clean, status-driven console.

## C3. Screens (build these 3)

### 1. Queue (home)
Encounters awaiting documentation: patient (deidentified id), status badge, last updated.
Statuses: `draft_ready`, `await_signoff`, `recorded`, `human_review`. Filter + search.

### 2. Encounter detail (main screen)
- **Two-pane:** left = source note / transcript; right = generated **SOAP note** + **extracted
  codes** (each editable, each with its rationale).
- **Validation flags** shown inline (missing section, ungrounded claim, invalid code).
- **Action bar (role-gated):** **Sign off** (clinician only -> triggers Recorder), **Edit &
  regenerate**, **Escalate**. Nothing is recorded until Sign off.

### 3. Review view
Filtered to `human_review`, with flags/reasons shown.

## C4. Backend endpoints (add to FastAPI if missing)
```
GET  /encounters?status=&q=
GET  /encounters/{id}            # source, soap, codes, flags, status
POST /encounters/{id}/signoff    # clinician -> writes record
POST /encounters/{id}/edit       # body: { soap?, codes? } -> regenerate/loop
POST /encounters/{id}/escalate   # body: { reason }
POST /encounters/{id}/run        # (optional) trigger the agent flow
```

## C5. Design principles
Status over decoration; sign-off is the most prominent control; always show code rationale
and validation flags (transparency).

## C6. Deferred
Audio/ASR input, full auth/SSO. (Agent-eval dashboards + deep transparency -> Part D.)

## C7. Phase
**Phase 7 — Console** (after Phase 6). ✅ Deliverable: Queue + Encounter detail (two-pane,
editable, sign-off) + Review, wired to FastAPI; only a clinician can sign off.

---

# Part D — Observability, evals & transparency (Langfuse)

Use **Langfuse** as the single observability + eval layer — industry-grade tracking (cost,
tokens, latency, errors, logs, every tool call, full per-step reasoning) plus eval dashboards.
Don't hand-build these views; instrument the agents and deep-link from the console.
(Phoenix/Arize optional later for deeper offline eval rigor.)

## D1. Setup
Self-host via Langfuse `docker-compose` (free) or cloud free tier. `.env`:
```
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_ENABLED=true
```
Add `langfuse` + `langfuse-langchain`.

## D2. Instrumentation
Attach the Langfuse CallbackHandler to the LangGraph run. Each encounter = one **trace**;
each agent = a **span**; each LLM/tool call = a nested observation. Capture inputs/outputs,
**tokens + cost** (map the NVIDIA model for cost), latency, errors. Group edit/regenerate
loops in a **session**. Tag: `encounter_id`, `procedure`, `role`, `status`.

## D3. Custom scores & flags
Push to Langfuse per trace: coding precision/recall/F1 (vs reference), **hallucination/
grounding** flag, SOAP completeness, schema-valid-first-try, **signed vs human_review**,
demographic slice.

## D4. Eval dashboards (accuracy, fairness/bias, reliability, cost)
Turn `test_cases.json` into a Langfuse **dataset**; run the system as an **experiment**;
attach D3 scores. Dashboards: coding accuracy + grounding, fairness parity across slices
(from `bias_eval.py`), reliability (schema-valid %, hallucinated-code %), cost per note.
Wire `run_eval.py` + `bias_eval.py` to log experiment runs so dashboards update each run.

## D5. Deep transparency
Langfuse's trace tree gives per-step reasoning, which tool was called, timings, cost, and an
audit-trail explorer per encounter for free. Edit/regenerate loops live in one session, so
original vs regenerated note/codes are both captured (side-by-side compare). From the
**Encounter detail** screen, add a "View full trace" **deep-link** to the Langfuse trace for
that `encounter_id`.

## D6. Compliance
Enable Langfuse **PII masking** (reuse Safe Harbor redaction). Data is deidentified/synthetic,
so tracing is fine; for real PHI, self-host Langfuse so trace data stays in your infra. State
this in the model card.

## D7. Phase
**Phase 8 — Observability & evals (Langfuse)** (after Phase 7). ✅ Deliverable: every encounter
fully traced (cost, tokens, latency, errors, tool calls, per-step reasoning); custom scores
logged; accuracy/fairness/reliability/cost dashboards live; "View full trace" deep-link from
the console; PII masking on.