"""Live end-to-end against NVIDIA NIM: representative flows + rationale + redaction proof."""
import sys, time
sys.path.insert(0, "/Users/khizar.sultan/Desktop/VD/portfolio/healthcare/ai")

from src import config
from src.models import PatientCase, Order, Condition, PriorTreatment
from src.graph import run_case
from src.governance.explain import explain
from src.llm.structured import STATS

print(f"backend={config.LLM_BACKEND} model={config.MODEL_NAME} remote={config.is_remote()}\n")

CONSENT = dict(purpose="prior_authorization",
               lawful_basis="Art.9(2)(h) provision of health care")


def case(pid, plan, cpt, disp, dx, tx, notes=""):
    return PatientCase(patient_id=pid, age=54, sex="female", plan_id=plan,
                       conditions=[Condition(code=c, display=d) for c, d in dx],
                       order=Order(cpt=cpt, display=disp),
                       prior_treatments=[PriorTreatment(type=t, date="2025-11-01") for t in tx],
                       notes=notes, **CONSENT)


scenarios = [
    ("APPROVE (happy path)",
     case("LIVE-APP", "PLAN_A", "73721", "MRI knee without contrast",
          [("M23.2", "Meniscus tear")], ["conservative_treatment"],
          "6 weeks PT + NSAIDs, persistent mechanical symptoms.")),
    ("DENY -> APPEAL (unsupportable)",
     case("LIVE-DEN", "PLAN_A", "73721", "MRI knee without contrast",
          [("Z00.00", "Routine exam")], [], "No knee pathology documented.")),
    ("NEEDS-INFO (missing documentation)",
     case("LIVE-NI", "PLAN_A", "95810", "Polysomnography",
          [("G47.33", "Obstructive sleep apnea")], [], "Sleep questionnaire not yet completed.")),
]

for title, c in scenarios:
    t0 = time.time()
    final = run_case(c)
    d = final.get("decision")
    print(f"=== {title} ===")
    print(f"  needs_pa={final.get('needs_pa')} coverage_ok={final.get('coverage_ok')} "
          f"decision={d.outcome.value if d else None} status={final.get('status')} "
          f"steps={final.get('attempt')}  ({time.time()-t0:.0f}s)")
    print("  rationale:")
    for line in explain(final).splitlines()[:6]:
        print("    " + line)
    print()

print(f"schema first-try pass: {STATS.first_try_ok}/{STATS.calls} = {STATS.first_try_rate:.0%} "
      f"(retried_ok={STATS.retried_ok}, failed={STATS.failed})")
