# Generating synthetic patients with Synthea

Synthea is a Java tool that emits synthetic FHIR R4 patient bundles. Run it **once**; the
output is git-ignored. All data is synthetic — no real patients, no PHI.

## Prerequisites
- Java (installed for this project via `brew install openjdk`). If `java -version` fails,
  add it to PATH for the shell:
  ```bash
  export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
  ```

## 1. Get the Synthea jar
```bash
cd healthcare/ai/data/synthea_output
curl -L -o synthea.jar \
  https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
```

## 2. Generate ~500 patients (FHIR R4, ICD-10 codes on)
```bash
java -jar synthea.jar \
  -p 500 \
  --exporter.fhir.export true \
  --exporter.baseDirectory ./ \
  --generate.append_numbers_to_person_names false \
  Massachusetts
```
FHIR bundles land in `data/synthea_output/fhir/*.json`.

## 3. Extract clean patient cases
```bash
cd healthcare/ai
./.venv/bin/python -m src.data_prep.extract_cases
```
This reads the FHIR bundles and writes `data/processed/case_XXX.json` — one `PatientCase`
each. Synthea provides realistic demographics and encounter history; `extract_cases.py`
maps each patient onto one of the five PA-relevant procedures and derives the PA coding
(documented in that script). The labeled evaluation set (`eval/test_cases.json`) is authored
separately so metrics are repeatable.
