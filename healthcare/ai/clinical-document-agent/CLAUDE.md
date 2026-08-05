# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. It is scoped to the **Clinical Documentation Agent**. See the repo-root `CLAUDE.md`
for monorepo-wide conventions, and the sibling `prior-authorization-agent/CLAUDE.md` — the two
agents share structure but differ in the ways noted below.

## What it is

A multi-agent system that turns a patient visit into a **signed** clinical note: draft a SOAP
note → extract ICD-10/CPT codes → validate → write to the record, but **only after a clinician
signs off**. This is a *generation* task, not a decision task, so the trust anchors are (1)
deterministic code validation and (2) a mandatory human sign-off — the model only drafts and
extracts. The live site demo is the slimmed port at `site/api/clinical-doc.py`.

## Control flow — a hand-rolled gate, not real LangGraph

**Important:** `src/graph.py::run()` is a plain Python `while` loop that *mirrors* a LangGraph
StateGraph with an interrupt — it is **not** an actual LangGraph graph (unlike the PA agent). Don't
look for `StateGraph`/nodes/edges here. The pipeline:

```
intake -> SOAP Writer -> Coder -> Validator
     -> blocking flags / low confidence -> human_review (break)
     -> otherwise -> signoff_fn(state)   [HUMAN-IN-THE-LOOP, injected]
            sign    -> Recorder -> recorded (break)
            edit    -> loop back through SOAP Writer/Coder (max MAX_EDIT_LOOPS=2) -> human_review
            reject  -> human_review (break)
```

Editing notes:

- **The sign-off is dependency-injected** as `signoff_fn(state) -> {"action", "signer", ...}` where
  `action ∈ {sign, edit, reject}`. The CLI, tests, and any future console/API all supply the
  clinician decision the same way. `_signoff_gate()` applies it to state.
- **Nothing reaches `recorder.run()` until `state["signed_off"]` is true.** This gate is the whole
  safety model — preserve it.
- State is a plain `dict` (not a typed schema like PA's `PAState`); every agent appends to
  `audit_log` via the shared `log()` (imported from `src.agents`).

## Trust anchors (do not weaken)

- **Deterministic code validation** (`src/codes/code_lookup.py`, applied by the Validator): every
  extracted code is checked against real ICD-10-CM / CPT sets; invented codes are dropped by a
  guard. A dropped code lowers confidence but is **not** blocking (the record was already
  protected). An unsupported claim or an incomplete note (missing a SOAP section) **is** blocking
  and routes to `human_review`.
- **Confidence gate:** below `MIN_CONFIDENCE` (0.7, `src/config.py`) routes to human review.
- **Redaction:** Intake Safe-Harbor–redacts the raw visit input (`src/compliance/redact.py`).
- **Mock EHR only:** the Recorder writes a FHIR-shaped record to `src/ehr/mock_ehr.py` — no real
  EHR integration.

## Config differs from the PA agent

- The provider env var here is **`LLM_PROVIDER`** (default `nvidia`), *not* `LLM_BACKEND`. Set
  `LLM_PROVIDER=ollama` for local. `src/llm/client.py` is still the single swap point.
- `src/config.py` is smaller: `MAX_RETRIES=2`, `MAX_EDIT_LOOPS=2`, `MIN_CONFIDENCE=0.7`.
- Structured LLM calls go through `src/llm/structured.py` (validate + retry), same pattern as PA.

## Commands

```bash
cp .env.example .env            # NVIDIA_API_KEY (free NVIDIA NIM) or LLM_PROVIDER=ollama
pip install -e .

python -m src.data_prep.extract_cases                        # build cases from synthetic fallback
python -m src.main --case data/processed/enc_001.json --signoff sign   # sign | edit | reject
python -m eval.run_eval                                      # agent system vs single-prompt baseline
pytest                                                       # offline tests (fake LLM via conftest)
pytest tests/test_codes.py::test_name                        # single test
```

`--signoff` stands in for the clinician at the mandatory gate (the same decision a console/API
would supply); `--feedback` is used only with `--signoff edit`.

## Data

- **Primary (real):** MIMIC-IV + MIMIC-IV-Note, PhysioNet-credentialed — see
  `src/data_prep/mimic_access.md`. Do **not** use real MIMIC before credentialing; `data/mimic/`
  is gitignored and never committed. No re-identification.
- **Dev fallback (default):** public/synthetic notes in `data/fallback/`, same `EncounterCase`
  shape — switching to MIMIC is a data swap, not a code change.

## Layout

`src/agents/` (intake, soap_writer, coder, validator, recorder) · `src/codes/` (ICD-10/CPT
lookup — the validation anchor) · `src/ehr/` (mock EHR) · `src/compliance/redact.py` ·
`src/governance/explain.py` · `src/llm/` · `eval/` · `tests/` (with `conftest.py` fake LLM) ·
`plan.md`.
