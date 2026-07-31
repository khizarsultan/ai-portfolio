# MIMIC access (primary data, credentialed)

1. **Credentialing** — complete PhysioNet credentialing: CITI "Data or Specimens Only Research"
   training + a signed Data Use Agreement. Start this first; it takes time.
2. **Dataset** — prefer **MIMIC-IV** (has ICD-10 codes) + the **MIMIC-IV-Note** module
   (discharge / radiology notes) for free-text input. MIMIC-III `NOTEEVENTS` is ICD-9.
3. **Tables**
   - Input note text: MIMIC-IV-Note `discharge` / `radiology`.
   - Ground-truth codes (for eval): `diagnoses_icd` / `procedures_icd` linked per admission
     (mind `icd_version`).
4. **Extraction** — extend `extract_cases.py` to read the credentialed extract and emit the
   same `EncounterCase` shape (encounter_id, age, sex, specialty, source_note, reference_codes).

## DUA rules (enforced in code + README)
- No attempt to re-identify patients.
- No redistribution. Data stays in `data/mimic/` (gitignored) — never committed.
- Deidentified/synthetic only until credentialing is complete.
