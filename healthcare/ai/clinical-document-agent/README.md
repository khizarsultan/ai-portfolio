# Clinical Documentation Agent

A multi-agent system that turns a patient visit into a finished clinical note: it drafts a
**SOAP note**, extracts **ICD-10 / CPT codes**, and writes the record — but **only after a
clinician signs off**. This attacks the documentation burden that eats up to ~35% of physician
time.

Because this is a *generation* task (not a decision), the trust anchors are:

1. **Deterministic code validation** — every extracted code is checked against real ICD-10-CM /
   CPT code sets; invented codes are dropped by a guard.
2. **A mandatory human sign-off** — nothing is written to the record until a clinician signs.
   The model only drafts and extracts.

## The agents

| Agent | Job |
|-------|-----|
| **Intake** | Normalize + Safe-Harbor redact the raw visit input into clean encounter text. |
| **SOAP Writer** | Draft the note (Subjective, Objective, Assessment, Plan), grounded in the source. |
| **Coder** | Extract ICD-10 diagnosis codes + CPT procedure/E&M codes, each with a rationale. |
| **Validator** | Deterministic checks: codes exist, all 4 SOAP sections present, claims trace to the source. Sets confidence + flags. |
| **Recorder** | Write the FHIR-shaped record to the mock EHR — only when `signed_off` is true. |

## Flow

```
intake -> SOAP Writer -> Coder -> Validator
     -> blocking flags / low confidence -> human_review
     -> otherwise -> await sign-off (HUMAN-IN-THE-LOOP, required)
            signed   -> Recorder -> recorded
            edited    -> back to SOAP Writer/Coder (loop, max 2) then human_review
            rejected  -> human_review
```

Every node appends to an append-only `audit_log`. A dropped invented code lowers confidence but
is not itself blocking (the guard already protected the record); an unsupported claim or an
incomplete note *is* blocking and routes to human review.

## Run it

```bash
cp .env.example .env            # set NVIDIA_API_KEY (free NVIDIA NIM) or use LLM_PROVIDER=ollama
pip install -e .
python -m src.data_prep.extract_cases                 # build cases from the synthetic fallback
python -m src.main --case data/processed/enc_001.json --signoff sign
python -m eval.run_eval                                # agent system vs single-prompt baseline
pytest                                                 # offline tests (fake LLM)
```

`--signoff` is `sign | reject | edit` — it stands in for the clinician at the mandatory gate,
the same decision a console/API would supply.

## Data

- **Primary:** MIMIC-IV (PhysioNet-credentialed) + MIMIC-IV-Note for free-text input; real
  `diagnoses_icd` / `procedures_icd` as ground-truth codes. See `src/data_prep/mimic_access.md`.
- **Dev fallback (now):** public/synthetic notes in `data/fallback/`, same `EncounterCase`
  shape — switching to MIMIC is a data swap, not a code change.

Do **not** use real MIMIC data before PhysioNet credentialing is complete. No re-identification;
`data/mimic/` is gitignored and never committed.

## Evaluation (plan §10)

Against a single-prompt baseline: SOAP completeness, coding precision/recall/F1 vs the reference
codes, and hallucinated-code rate. The agent system produces better-grounded notes and safer
codes — plus a sign-off gate a single prompt cannot provide.

## Model / system card

- **What it does:** drafts a SOAP note and codes; a clinician signs before anything is recorded.
- **LLM:** NVIDIA NIM (hosted, free) or Ollama (local). Hosted means data leaves the machine —
  fine here because data is deidentified/synthetic; real PHI would need a BAA or self-hosting.
- **Limits:** open models are weaker at strict JSON, so the anchors are deterministic (code
  validation) and human (sign-off); the LLM only drafts/extracts.
- **Out of scope:** no audio/ASR (text input assumed), no real EHR integration (mock only), not
  certified HIPAA-compliant infrastructure.

## Live demo

A self-contained port of this pipeline runs on the portfolio site at `/demos/clinical-doc`
(`site/api/clinical-doc.py`) — bounded to 5 synthetic encounters, one per branch.
