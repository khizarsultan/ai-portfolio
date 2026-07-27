"""Mock insurance payer. Deterministic so evals are repeatable. Never calls a real API."""
from __future__ import annotations
from src.models import PatientCase, Packet, Decision, Outcome
from src.payer import rules_engine


def check_eligibility(case: PatientCase) -> tuple[bool, str]:
    """Coverage active AND the ordered procedure is a covered benefit under the plan."""
    if not case.coverage_active:
        return False, "Member coverage is not active."
    if not rules_engine.is_covered(case.plan_id, case.order.cpt):
        return False, (f"Procedure {case.order.cpt} is a non-covered benefit under "
                       f"plan {case.plan_id}.")
    return True, "Coverage active and procedure is a covered benefit."


def decide(packet: Packet) -> Decision:
    """Adjudicate a submitted PA packet via the deterministic rules engine."""
    return rules_engine.evaluate(packet)
