"""Author the labeled evaluation set -> eval/test_cases.json (deterministic, repeatable).

Each entry pairs a PatientCase with its expected outcome label:
  AUTO_CLEAR   no PA required
  NOT_COVERED  PA required but procedure not a covered benefit (or coverage inactive)
  APPROVED     PA required, covered, medical necessity established
  NEEDS_INFO   necessity supported but required documentation permanently absent
  DENIED       diagnosis does not support the procedure (and appeal cannot fix it)
"""
from __future__ import annotations
import json
from pathlib import Path

CASES = []


def add(cid, label, expected_needs_pa, expected_status, expected_decision, case):
    CASES.append({
        "id": cid, "expected_label": label,
        "expected_needs_pa": expected_needs_pa,
        "expected_status": expected_status,
        "expected_decision": expected_decision,
        "case": case,
    })


def C(pid, plan, cpt, disp, dx, tx, active=True, notes=""):
    return {
        "patient_id": pid, "age": 52, "sex": "female" if int(pid[-1]) % 2 else "male",
        "plan_id": plan, "coverage_active": active,
        "conditions": [{"code": c, "display": d} for c, d in dx],
        "order": {"cpt": cpt, "display": disp},
        "prior_treatments": [{"type": t, "date": "2025-11-01", "description": t} for t in tx],
        "notes": notes,
        "purpose": "prior_authorization",
        "lawful_basis": "Art.9(2)(h) provision of health care",
    }


KNEE = ("73721", "MRI knee without contrast")
BRAIN = ("70551", "MRI brain without contrast")
CT = ("74177", "CT abdomen and pelvis with contrast")
SLEEP = ("95810", "Polysomnography (sleep study)")
PT = ("97110", "Physical therapy - therapeutic exercise")

# --- AUTO_CLEAR: PT (97110) never requires PA ---------------------------------
for i, plan in enumerate(["PLAN_A", "PLAN_B", "PLAN_A", "PLAN_B", "PLAN_A"]):
    add(f"clear_{i+1}", "AUTO_CLEAR", False, "done", None,
        C(f"AC0000{i}", plan, *PT, [("M54.5", "Low back pain")], [], notes="Routine PT referral."))

# --- NOT_COVERED: PLAN_B doesn't cover brain MRI / CT abdomen; + one inactive --
add("cov_1", "NOT_COVERED", True, "human_review", None,
    C("NC00001", "PLAN_B", *BRAIN, [("G43.909", "Migraine")], []))
add("cov_2", "NOT_COVERED", True, "human_review", None,
    C("NC00002", "PLAN_B", *CT, [("R10.9", "Abdominal pain")], []))
add("cov_3", "NOT_COVERED", True, "human_review", None,
    C("NC00003", "PLAN_B", *BRAIN, [("R51.9", "Headache")], []))
add("cov_4", "NOT_COVERED", True, "human_review", None,
    C("NC00004", "PLAN_A", *KNEE, [("M23.2", "Meniscus tear")],
      ["conservative_treatment"], active=False, notes="Coverage lapsed."))

# --- APPROVED: PA required, covered, full evidence ----------------------------
add("appr_1", "APPROVED", True, "done", "APPROVED",
    C("AP00001", "PLAN_A", *KNEE, [("M23.2", "Meniscus tear")],
      ["conservative_treatment"], notes="6 weeks PT + NSAIDs, persistent pain."))
add("appr_2", "APPROVED", True, "done", "APPROVED",
    C("AP00002", "PLAN_A", *SLEEP, [("G47.33", "Obstructive sleep apnea")],
      ["sleep_questionnaire"], notes="Epworth 14, witnessed apneas."))
add("appr_3", "APPROVED", True, "done", "APPROVED",
    C("AP00003", "PLAN_A", *BRAIN, [("G43.909", "Migraine with aura")], [],
      notes="New neurologic deficit."))
add("appr_4", "APPROVED", True, "done", "APPROVED",
    C("AP00004", "PLAN_A", *CT, [("K35.80", "Acute appendicitis")], [],
      notes="RLQ pain, fever."))
add("appr_5", "APPROVED", True, "done", "APPROVED",
    C("AP00005", "PLAN_B", *KNEE, [("M17.11", "Unilateral knee OA")],
      ["conservative_treatment"], notes="Failed conservative care."))
add("appr_6", "APPROVED", True, "done", "APPROVED",
    C("AP00006", "PLAN_B", *SLEEP, [("G47.30", "Sleep apnea unspecified")],
      ["sleep_questionnaire"]))
add("appr_7", "APPROVED", True, "done", "APPROVED",
    C("AP00007", "PLAN_A", *KNEE, [("S83.5", "ACL sprain"), ("M25.561", "Knee pain")],
      ["conservative_treatment"], notes="Instability after injury; bracing + PT tried."))
add("appr_8", "APPROVED", True, "done", "APPROVED",
    C("AP00008", "PLAN_A", *SLEEP, [("G47.33", "OSA")],
      ["sleep_questionnaire"], notes="BMI 34, hypertension."))
add("appr_9", "APPROVED", True, "done", "APPROVED",
    C("AP00009", "PLAN_A", *BRAIN, [("G40.909", "Epilepsy")], [], notes="First seizure workup."))

# --- NEEDS_INFO (stuck): dx supports it, required documentation absent ---------
add("ni_1", "NEEDS_INFO", True, "human_review", "NEEDS_INFO",
    C("NI00001", "PLAN_A", *KNEE, [("M23.2", "Meniscus tear")], [],
      notes="No conservative treatment on record yet."))
add("ni_2", "NEEDS_INFO", True, "human_review", "NEEDS_INFO",
    C("NI00002", "PLAN_A", *SLEEP, [("G47.33", "Suspected OSA")], [],
      notes="No sleep questionnaire completed."))
add("ni_3", "NEEDS_INFO", True, "human_review", "NEEDS_INFO",
    C("NI00003", "PLAN_A", *KNEE, [("M25.561", "Knee pain")], [],
      notes="Awaiting PT documentation."))
add("ni_4", "NEEDS_INFO", True, "human_review", "NEEDS_INFO",
    C("NI00004", "PLAN_B", *SLEEP, [("G47.30", "Sleep apnea unspecified")], []))
add("ni_5", "NEEDS_INFO", True, "human_review", "NEEDS_INFO",
    C("NI00005", "PLAN_B", *KNEE, [("M17.11", "Knee OA")], []))
add("ni_6", "NEEDS_INFO", True, "human_review", "NEEDS_INFO",
    C("NI00006", "PLAN_A", *SLEEP, [("G47.33", "OSA")], [], notes="Questionnaire pending."))

# --- DENIED (stuck): diagnosis does not establish necessity -------------------
add("den_1", "DENIED", True, "human_review", "DENIED",
    C("DN00001", "PLAN_A", *KNEE, [("Z00.00", "Routine exam")],
      ["conservative_treatment"], notes="No knee pathology documented."))
add("den_2", "DENIED", True, "human_review", "DENIED",
    C("DN00002", "PLAN_A", *BRAIN, [("Z00.00", "Routine exam")], [],
      notes="No neurologic indication."))
add("den_3", "DENIED", True, "human_review", "DENIED",
    C("DN00003", "PLAN_A", *CT, [("M54.5", "Low back pain")], [],
      notes="No abdominal pathology."))
add("den_4", "DENIED", True, "human_review", "DENIED",
    C("DN00004", "PLAN_A", *SLEEP, [("E66.9", "Obesity")],
      ["sleep_questionnaire"], notes="No sleep-disorder diagnosis."))
add("den_5", "DENIED", True, "human_review", "DENIED",
    C("DN00005", "PLAN_B", *KNEE, [("I10", "Hypertension")],
      ["conservative_treatment"], notes="Unrelated diagnosis."))
add("den_6", "DENIED", True, "human_review", "DENIED",
    C("DN00006", "PLAN_A", *CT, [("Z00.00", "Routine exam")], [],
      notes="Screening request without indication."))


def main() -> None:
    out = Path(__file__).resolve().parent / "test_cases.json"
    out.write_text(json.dumps(CASES, indent=2))
    print(f"Wrote {len(CASES)} labeled cases to {out}")


if __name__ == "__main__":
    main()
