# Prior Authorization Agent — Implementation Plan

## 1. Goal

Build an agentic system that handles a medical **prior authorization (PA)** request end to end:
decide if PA is needed, verify insurance coverage, assemble the request, submit it, and
automatically appeal denials — with a human doing final review only.

This is a portfolio project. It must run fully on a laptop with **synthetic data** (no real
patient data, no real insurer). The "insurance company" is a mock service we build.

Success = given a synthetic patient + a procedure order, the system produces a correct
PA decision (approved / denied / needs-info) with a full audit trail, and beats a naive
single-prompt baseline on our eval set.

---

## 2. What we're building (plain version)

Instead of one big AI, we build a **team of small agents**, each with one job. They hand
work to each other and branch based on what happens.

- **Checker** — Does this order even need PA? (rules differ per insurer)
- **Verifier** — Is the patient's coverage active and does the plan cover this?
- **Assembler** — Pull the patient's records and build a complete, correct PA packet.
- **Submitter** — Send the packet to the (mock) payer and read the response.
- **Appealer** — If denied, find the missing justification and draft an appeal, then resubmit.

An **orchestrator** wires them together and enforces loop limits so it can't retry forever.

---

## 3. Architecture

Stateful graph (LangGraph). Nodes = agents. Edges branch on results.

```
[intake] 
   -> Checker (needs PA?)
        -> NO  -> [end: auto-clear, no PA required]
        -> YES -> Verifier (coverage active + covered?)
                     -> NOT COVERED -> [end: flag for human]
                     -> COVERED     -> Assembler (build packet)
                                          -> Submitter (send to mock payer)
                                               -> APPROVED   -> [end: done]
                                               -> NEEDS_INFO -> Assembler (add missing) [loop, max 2]
                                               -> DENIED     -> Appealer (draft appeal)
                                                                   -> Submitter (resubmit) [loop, max 2]
```

Loop caps: after 2 needs-info cycles or 2 appeal cycles, stop and route to human.

Every node appends to a shared `audit_log` so we can show the full trail (this is the
selling point for a healthcare portfolio — traceability).

---

## 4. Tech stack

- **Python 3.11+**
- **LangGraph** — agent orchestration (handles the branching/looping graph cleanly)
- **LangChain** — LLM + tool plumbing
- **Anthropic Claude** (`claude-sonnet` for agents; make the model a config value)
- **Pydantic v2** — state and data schemas
- **Synthea** — generates synthetic FHIR patient records (Java tool, run once)
- **Mock Payer** — our own Python module: rules engine + decision service
- **FastAPI** (optional, Phase 5) — a small demo endpoint
- **pytest** — tests + eval harness
- **python-dotenv** — config / API keys

Do NOT call any real insurance API. Do NOT use real patient data.

---

## 5. Repo structure

```
prior-auth-agent/
├── plan.md
├── README.md
├── pyproject.toml
├── .env.example              # ANTHROPIC_API_KEY, MODEL_NAME
├── data/
│   ├── synthea_output/       # generated FHIR bundles (gitignored)
│   ├── processed/            # extracted patient cases (json)
│   └── payer_rules/
│       ├── pa_required.yaml   # which CPT codes need PA per plan
│       └── medical_necessity.yaml  # approval criteria per procedure
├── src/
│   ├── state.py              # PAState (shared graph state)
│   ├── models.py             # Pydantic: Patient, Order, Packet, Decision
│   ├── graph.py              # LangGraph wiring + conditional edges
│   ├── agents/
│   │   ├── checker.py
│   │   ├── verifier.py
│   │   ├── assembler.py
│   │   ├── submitter.py
│   │   └── appealer.py
│   ├── payer/
│   │   ├── mock_payer.py     # decision service (approve/deny/needs-info)
│   │   └── rules_engine.py   # loads + evaluates payer_rules/*.yaml
│   ├── data_prep/
│   │   ├── run_synthea.md    # how to generate data
│   │   └── extract_cases.py  # FHIR bundle -> clean patient case json
│   └── main.py               # run one case end to end (CLI)
├── eval/
│   ├── test_cases.json       # labeled scenarios (expected outcome)
│   ├── baseline.py           # single-prompt baseline for comparison
│   └── run_eval.py           # metrics vs baseline
└── tests/
    ├── test_agents.py
    ├── test_payer.py
    └── test_graph.py
```

---

## 6. Data setup

### Synthea (synthetic patients)
- Generate ~500 synthetic patients (FHIR R4 bundles).
- `extract_cases.py` reads each bundle and pulls: patient id/age/sex, active
  Conditions (ICD-10), Procedures ordered (CPT), Encounters, prior treatments.
- Output = a list of clean `PatientCase` json objects in `data/processed/`.

### CMS public claims data (optional enrichment)
- Use only to make procedure/diagnosis distributions realistic (which CPT codes are
  common, typical pairings). Do not need PII. Keep this lightweight — Synthea is the
  primary source.

### Mock Payer rules (we author these)
- `pa_required.yaml`: map of `plan_id -> [CPT codes that require PA]`.
- `medical_necessity.yaml`: per CPT, the criteria that must be present in the packet
  to approve (e.g. MRI knee 73721 requires: prior conservative treatment documented +
  matching diagnosis code). Missing criteria -> `needs_info`. Wrong/absent justification
  -> `denied`.

This rules file is what makes denials/appeals meaningful and testable.

---

## 7. Component specs

### State (`state.py`)
```python
class PAState(TypedDict):
    case: PatientCase          # patient + order
    needs_pa: bool | None
    coverage_ok: bool | None
    packet: Packet | None
    decision: Decision | None  # APPROVED | DENIED | NEEDS_INFO
    denial_reason: str | None
    attempt: int               # loop counter
    audit_log: list[str]       # append-only trail
    status: str                # running | done | human_review
```

### Checker (`agents/checker.py`)
- **In:** patient plan_id + order CPT code
- **Job:** look up `pa_required.yaml`; if ambiguous, ask Claude to reason over the plan text
- **Out:** `needs_pa: bool` + audit entry

### Verifier (`agents/verifier.py`)
- **In:** patient coverage info + order
- **Job:** call mock payer's eligibility check (coverage active? procedure in benefits?)
- **Out:** `coverage_ok: bool` + audit entry

### Assembler (`agents/assembler.py`)
- **In:** patient case, `denial_reason` (if looping)
- **Job:** Claude pulls relevant conditions/procedures/notes and builds a `Packet`
  (diagnosis codes, clinical justification, attachments list). On a needs-info/appeal
  loop, it specifically targets the missing/challenged item.
- **Out:** `Packet` + audit entry

### Submitter (`agents/submitter.py`)
- **In:** `Packet`
- **Job:** send to `mock_payer.decide(packet)`; record the decision
- **Out:** `Decision` (+ `denial_reason` if denied) + audit entry

### Appealer (`agents/appealer.py`)
- **In:** `Packet` + `denial_reason`
- **Job:** Claude reads the denial reason, finds supporting evidence in the patient case,
  drafts an appeal letter, updates the packet
- **Out:** revised `Packet` + audit entry

### Mock Payer (`payer/mock_payer.py`)
- `check_eligibility(case) -> bool`
- `decide(packet) -> Decision` using `rules_engine`:
  - all criteria met -> APPROVED
  - criteria present but incomplete evidence -> NEEDS_INFO
  - criteria not met / wrong justification -> DENIED (with reason)
- Deterministic (rules-based) so eval is repeatable.

---

## 8. Implementation phases (build in this order)

**Phase 1 — Data foundation**
- Set up repo, pyproject, .env.example, README skeleton.
- Write `run_synthea.md` and generate ~500 patients.
- Build `extract_cases.py` -> `PatientCase` json.
- Author `pa_required.yaml` and `medical_necessity.yaml` for ~5 procedures
  (e.g. MRI knee, MRI brain, CT abdomen, sleep study, PT).
- ✅ Deliverable: `data/processed/*.json` + rules files, plus a test.

**Phase 2 — Mock payer + rules engine**
- Implement `rules_engine.py` and `mock_payer.py`.
- Unit tests: each procedure yields approve / needs-info / deny for crafted packets.
- ✅ Deliverable: passing `tests/test_payer.py`.

**Phase 3 — Agents (no graph yet)**
- Implement all 5 agents as standalone functions taking/returning `PAState`.
- Test each in isolation with a fixed case.
- ✅ Deliverable: passing `tests/test_agents.py`.

**Phase 4 — Graph orchestration**
- Wire agents in `graph.py` with the conditional edges + loop caps from §3.
- `main.py`: run one case end to end, print decision + audit_log.
- ✅ Deliverable: `python -m src.main --case <id>` runs full flow.

**Phase 5 — Eval + demo**
- Build `eval/test_cases.json` (~30 labeled cases: mix of no-PA, approve, needs-info->approve,
  deny->appeal->approve, deny->stay-denied).
- `baseline.py`: one Claude prompt that just answers "approve/deny" with no agents.
- `run_eval.py`: report metrics (see §9) for agent system vs baseline.
- (Optional) FastAPI `/submit` endpoint + a short README with a demo GIF.
- ✅ Deliverable: eval report showing agents beat baseline.

---

## 9. Evaluation metrics

Run on `eval/test_cases.json`:
- **PA-needed accuracy** — Checker correct vs labels.
- **Final-decision accuracy** — end state matches expected outcome.
- **Appeal recovery rate** — % of deniable-but-justifiable cases the Appealer turns into approval.
- **Avg agent steps / case** — efficiency (watch for loop abuse).
- **Audit completeness** — every case has a full, readable trail (yes/no).

Compare all against the single-prompt baseline. The story: the agent system is more
accurate on the multi-step cases (appeals, needs-info) that a single prompt fumbles.

---

## 10. Out of scope (state clearly in README)

- No real payer APIs, no real EHR, no PHI.
- Not HIPAA-compliant infra — this is a demo on synthetic data.
- No UI beyond an optional FastAPI endpoint / CLI.

---

## 11. Getting started (fill in as you build)

```bash
# setup
cp .env.example .env         # add ANTHROPIC_API_KEY
pip install -e .

# generate data (see src/data_prep/run_synthea.md)
python -m src.data_prep.extract_cases

# run one case
python -m src.main --case data/processed/case_001.json

# eval
python -m eval.run_eval
```

---

## 12. Notes for the implementer

- Keep the model name in config; don't hardcode.
- Prefer small, surgical functions per agent; the graph should read like §3.
- Make the mock payer deterministic so eval is repeatable.
- Log every agent decision to `audit_log` — traceability is the point of this project.
- Data is synthetic (Synthea + CMS-informed). US-based sources; note this in the README.