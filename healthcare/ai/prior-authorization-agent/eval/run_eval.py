"""Evaluate the agent system vs the single-prompt baseline on the labeled set.

    python -m eval.run_eval [--limit N] [--no-baseline]

Metrics (plan §9):
  PA-needed accuracy, final-decision accuracy, appeal-recovery rate,
  avg agent steps/case, audit completeness. Agent vs baseline on final-decision accuracy.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.models import PatientCase, Outcome
from src.graph import run_case
from src.llm.structured import STATS
from src.governance.explain import explain
from eval import baseline

TESTS = Path(__file__).resolve().parent / "test_cases.json"


def agent_label(final) -> str:
    if not final.get("needs_pa"):
        return "AUTO_CLEAR"
    if not final.get("coverage_ok"):
        return "NOT_COVERED"
    d = final.get("decision")
    return d.outcome.value if d else "NEEDS_INFO"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-baseline", action="store_true")
    args = ap.parse_args()

    cases = json.loads(TESTS.read_text())
    if args.limit:
        cases = cases[:args.limit]

    STATS.reset()
    pa_correct = final_correct = base_correct = 0
    steps_total = audit_ok = 0
    appealed = appeal_recovered = 0
    hallucination_cases = rationale_ok = 0
    rows = []

    for tc in cases:
        case = PatientCase(**tc["case"])
        final = run_case(case, expected_label=tc["expected_label"])  # planv4: log correctness score
        a_label = agent_label(final)

        pa_hit = final.get("needs_pa") == tc["expected_needs_pa"]
        final_hit = a_label == tc["expected_label"]
        pa_correct += pa_hit
        final_correct += final_hit
        steps_total += final.get("attempt", 0)
        audit_ok += 1 if final.get("audit_log") else 0

        trail = " ".join(final.get("audit_log", []))
        if "DENIED" in trail:
            appealed += 1
            if a_label == "APPROVED":
                appeal_recovered += 1
        if "Hallucination guard" in trail:
            hallucination_cases += 1
        if explain(final).strip():
            rationale_ok += 1

        b_label = "-"
        if not args.no_baseline:
            b_label = baseline.classify(case)
            base_correct += b_label == tc["expected_label"]

        mark = "ok " if final_hit else "MISS"
        rows.append(f"  {mark} {tc['id']:<8} exp={tc['expected_label']:<11} "
                    f"agent={a_label:<11} base={b_label:<11} steps={final.get('attempt')}")

    n = len(cases)
    print("\n".join(rows))
    print("\n===== Prior-Authorization Agent — Evaluation =====")
    print(f"Cases:                     {n}")
    print(f"PA-needed accuracy:        {pa_correct}/{n} = {pa_correct/n:.0%}")
    print(f"Final-decision accuracy:   {final_correct}/{n} = {final_correct/n:.0%}  (AGENT)")
    if not args.no_baseline:
        print(f"Final-decision accuracy:   {base_correct}/{n} = {base_correct/n:.0%}  (BASELINE, single prompt)")
        print(f"Agent uplift:              {(final_correct-base_correct)/n:+.0%}")
    rec = f"{appeal_recovered}/{appealed}" if appealed else "n/a (no denials hit the appeal path)"
    print(f"Appeal recovery rate:      {rec}")
    print(f"Avg agent steps / case:    {steps_total/n:.1f}")
    print(f"Audit completeness:        {audit_ok}/{n} = {audit_ok/n:.0%}")
    print("--- Governance (planv2 B5) ---")
    print(f"Schema first-try pass rate: {STATS.first_try_ok}/{STATS.calls} = {STATS.first_try_rate:.0%}"
          f"  (retried_ok={STATS.retried_ok}, failed={STATS.failed})")
    print(f"Cases with dropped/halluc. codes: {hallucination_cases}/{n}")
    print(f"Transparency (rationale present):  {rationale_ok}/{n} = {rationale_ok/n:.0%}")


if __name__ == "__main__":
    main()
