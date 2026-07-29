"""Run one prior-authorization case end to end and print the decision + audit trail.

    python -m src.main --case data/processed/case_001.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.models import PatientCase
from src.graph import run_case
from src.governance.explain import explain


def load_case(path: str) -> PatientCase:
    return PatientCase(**json.loads(Path(path).read_text()))


def main() -> None:
    ap = argparse.ArgumentParser(description="Prior Authorization Agent")
    ap.add_argument("--case", required=True, help="Path to a PatientCase JSON file")
    ap.add_argument("--role", default="clinician",
                    help="RBAC role submitting the request (clinician|reviewer|admin)")
    args = ap.parse_args()

    case = load_case(args.case)
    print(f"\n=== Case {case.patient_id} | plan {case.plan_id} | "
          f"order {case.order.cpt} ({case.order.display}) | role {args.role} ===\n")

    final = run_case(case, actor_role=args.role)

    print("--- Audit trail ---")
    for line in final["audit_log"]:
        print(line)

    decision = final.get("decision")
    print("\n--- Result ---")
    print(f"Needs PA:    {final.get('needs_pa')}")
    print(f"Coverage OK: {final.get('coverage_ok')}")
    if decision:
        print(f"Decision:    {decision.outcome.value} — {decision.reason}")
    print(f"Status:      {final.get('status')}")
    print(f"Agent steps: {final.get('attempt')}")

    print("\n--- Plain-English rationale ---")
    print(explain(final))

    if final.get("packet") and final["packet"].appeal_letter:
        print("\n--- Appeal letter ---")
        print(final["packet"].appeal_letter)


if __name__ == "__main__":
    main()
