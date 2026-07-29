"""Transparency (planv2 B3.4): turn the audit trail + decision into a plain-English rationale
a human reviewer can read. Every decision must produce one."""
from __future__ import annotations


def explain(final: dict) -> str:
    """Human-readable rationale for a completed run."""
    case = final["case"]
    lines = [f"Prior-authorization rationale for order {case.order.cpt} "
             f"({case.order.display}) under plan {case.plan_id}:"]

    if final.get("needs_pa") is False:
        lines.append("• This procedure does not require prior authorization under the plan, "
                     "so it was auto-cleared. No further review needed.")
        return "\n".join(lines)

    lines.append("• Prior authorization IS required for this procedure under the plan.")
    if final.get("coverage_ok") is False:
        lines.append("• Coverage check failed (inactive coverage or non-covered benefit), "
                     "so the request was routed to a human reviewer.")
        return "\n".join(lines)

    lines.append("• Coverage is active and the procedure is a covered benefit.")
    decision = final.get("decision")
    outcome = decision.outcome.value if decision else None
    status = final.get("status")
    if decision:
        lines.append(f"• Payer decision: {outcome} — {decision.reason}")
    # The loop counters track decisions SEEN; the remediating agent runs only on the
    # non-capped ones, so when a cap trips the last decision produced no revision/appeal.
    revisions = final.get("needs_info_loops", 0)
    if status == "human_review" and outcome == "NEEDS_INFO":
        revisions -= 1
    if revisions:
        lines.append(f"• The packet was revised {revisions} time(s) to add "
                     "requested documentation.")
    appeals = final.get("appeal_loops", 0)
    if status == "human_review" and outcome == "DENIED":
        appeals -= 1
    if appeals:
        lines.append(f"• {appeals} appeal(s) were drafted and resubmitted.")
    if status == "human_review":
        lines.append("• OUTCOME: escalated to a human reviewer (no automated denial is final).")
    elif status == "done" and decision and decision.outcome.value == "APPROVED":
        lines.append("• OUTCOME: approved and complete.")

    lines.append("\nDecision path (audit trail):")
    lines.extend(f"  {entry}" for entry in final.get("audit_log", []))
    return "\n".join(lines)
