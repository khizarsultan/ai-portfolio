"""Convert Synthea FHIR R4 bundles into clean PatientCase JSON files.

Synthea supplies realistic demographics and encounter history. Because Synthea codes
conditions in SNOMED and its random procedures rarely line up with our five PA-relevant
CPTs, this extractor maps each patient onto one target procedure and derives the
PA-relevant coding deterministically (seeded by the patient id, so runs are repeatable):

  ~55% fully-supported  (approvable)
  ~25% missing prior treatment  (needs-info -> approvable on loop if evidence exists)
  ~20% unsupported diagnosis  (deniable)

Real Synthea conditions are preserved in `notes` for context. No randomness module is used.
"""
from __future__ import annotations
import hashlib
import json
from datetime import date
from pathlib import Path

import yaml

from src.config import SYNTHEA_OUT, PROCESSED, RULES_DIR
from src.models import PatientCase, Condition, Order, PriorTreatment

TARGET_CPTS = ["73721", "70551", "74177", "95810", "97110"]
PLANS = ["PLAN_A", "PLAN_B"]


def _seed(patient_id: str) -> int:
    return int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)


def _age(birth: str) -> int:
    try:
        y, m, d = (int(x) for x in birth.split("T")[0].split("-"))
        today = date(2026, 1, 1)
        return today.year - y - ((today.month, today.day) < (m, d))
    except Exception:
        return 45


def _parse_bundle(bundle: dict) -> dict | None:
    pid, age, sex, conditions = None, 45, "unknown", []
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        rt = res.get("resourceType")
        if rt == "Patient":
            pid = res.get("id")
            age = _age(res.get("birthDate", ""))
            sex = res.get("gender", "unknown")
        elif rt == "Condition":
            cc = res.get("code", {})
            disp = cc.get("text") or (cc.get("coding") or [{}])[0].get("display", "")
            if disp:
                conditions.append(disp)
    if not pid:
        return None
    return {"pid": pid, "age": age, "sex": sex, "conditions": conditions[:12]}


def _build_case(info: dict, necessity: dict) -> PatientCase:
    seed = _seed(info["pid"])
    cpt = TARGET_CPTS[seed % len(TARGET_CPTS)]
    plan = PLANS[(seed // 7) % len(PLANS)]
    crit = necessity[cpt]
    req_dx = crit["required_diagnoses"]
    req_tx = crit.get("required_prior_treatments") or []

    flavor = seed % 100
    supported = flavor < 55
    needs_info = 55 <= flavor < 80        # dx present, prior tx omitted from record
    # else deniable: no supporting dx

    conditions: list[Condition] = []
    prior: list[PriorTreatment] = []
    if supported or needs_info:
        conditions.append(Condition(code=req_dx[0], display=crit["display"] + " indication"))
        if supported and req_tx:
            prior.append(PriorTreatment(type=req_tx[0], date="2025-11-01",
                                        description=f"{req_tx[0]} documented prior to imaging"))
        # needs_info: required prior treatment intentionally absent from record
    else:
        # deniable: an unrelated diagnosis, none of the required ones
        conditions.append(Condition(code="Z00.00", display="General adult medical exam"))

    note = "Synthea history: " + ("; ".join(info["conditions"][:6]) or "none recorded")
    return PatientCase(
        patient_id=info["pid"][:8],
        age=info["age"], sex=info["sex"], plan_id=plan, coverage_active=True,
        conditions=conditions,
        order=Order(cpt=cpt, display=crit["display"]),
        prior_treatments=prior,
        notes=note,
        purpose="prior_authorization",
        lawful_basis="Art.9(2)(h) provision of health care",
    )


def main() -> None:
    with open(RULES_DIR / "medical_necessity.yaml") as f:
        necessity = yaml.safe_load(f)

    fhir_dir = SYNTHEA_OUT / "fhir"
    bundles = sorted(fhir_dir.glob("*.json")) if fhir_dir.exists() else []
    # skip Synthea's practitioner/hospital info bundles
    bundles = [b for b in bundles if not b.name.startswith(("practitionerInformation",
                                                            "hospitalInformation"))]
    if not bundles:
        raise SystemExit(
            f"No FHIR bundles in {fhir_dir}. Run Synthea first (see run_synthea.md).")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    n = 0
    for b in bundles:
        try:
            bundle = json.loads(b.read_text())
        except Exception:
            continue
        info = _parse_bundle(bundle)
        if not info:
            continue
        case = _build_case(info, necessity)
        n += 1
        out = PROCESSED / f"case_{n:03d}.json"
        out.write_text(case.model_dump_json(indent=2))
    print(f"Wrote {n} patient cases to {PROCESSED}")


if __name__ == "__main__":
    main()
