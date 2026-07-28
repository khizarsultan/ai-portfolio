"""Prior Authorization Agent — live multi-agent pipeline on a Vercel Python function.

A faithful, self-contained port of healthcare/ai/src (LangGraph 5-agent system). No LangChain/
LangGraph is bundled: the orchestration is plain Python and the LLM is reached over stdlib HTTPS
to NVIDIA NIM's OpenAI-compatible endpoint — tiny cold start, well under the 250MB limit.

Faithful to the real system:
  - The payer DECISION is deterministic (rules engine), never the LLM. The LLM only reasons,
    extracts documented evidence, and drafts the appeal.
  - A hallucination guard drops any ICD-10 code the model invents.
  - Off-machine calls send a HIPAA Safe-Harbor-redacted case view (compliance.redact).
  - Loop caps (needs-info / appeal) and human-review escalation — no autonomous denial.

Input is a bounded picker of 5 synthetic cases (not an open prompt) so a public demo can run
live on the owner's NIM key without becoming a free-for-all LLM. Data here is synthetic — no PHI.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

# --- config (server-side only) ---------------------------------------------
API_KEY = os.getenv("NVIDIA_API_KEY")
BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
MODEL = os.getenv("MODEL_NAME", "meta/llama-3.3-70b-instruct")
MAX_RETRIES = 2
MAX_NEEDS_INFO_LOOPS = 2
MAX_APPEAL_LOOPS = 2

# --- payer rules (embedded from data/payer_rules/*.yaml) --------------------
PA_REQUIRED = {
    "PLAN_A": ["73721", "70551", "74177", "95810"],
    "PLAN_B": ["73721", "95810", "70551", "74177"],
}
PLANS = {
    "PLAN_A": {"name": "Commercial PPO", "covered_cpt": ["73721", "70551", "74177", "95810", "97110"]},
    "PLAN_B": {"name": "Basic HMO", "covered_cpt": ["73721", "95810", "97110"]},
}
NECESSITY = {
    "73721": {"display": "MRI knee without contrast",
              "required_diagnoses": ["M23.2", "M17.11", "S83.5", "M25.561"],
              "required_prior_treatments": ["conservative_treatment"]},
    "70551": {"display": "MRI brain without contrast",
              "required_diagnoses": ["G43.909", "R51.9", "G40.909"], "required_prior_treatments": []},
    "74177": {"display": "CT abdomen and pelvis with contrast",
              "required_diagnoses": ["R10.9", "K35.80", "R19.00"], "required_prior_treatments": []},
    "95810": {"display": "Polysomnography (sleep study)",
              "required_diagnoses": ["G47.33", "G47.30"],
              "required_prior_treatments": ["sleep_questionnaire"]},
    "97110": {"display": "Physical therapy - therapeutic exercise",
              "required_diagnoses": ["M54.5", "M25.561", "M23.2"], "required_prior_treatments": []},
}
_EXTRA_ICD10 = {"Z00.00", "E66.9", "I10", "R19.00"}
KNOWN_ICD10 = set(_EXTRA_ICD10)
for _c in NECESSITY.values():
    KNOWN_ICD10.update(_c["required_diagnoses"])

# --- 5 curated synthetic cases, one per pipeline branch ---------------------
CASES = [
    {
        "id": "pt-ptx", "title": "Physical therapy — no PA needed",
        "path": "Auto-cleared", "plan_id": "PLAN_A",
        "order": {"cpt": "97110", "display": "Physical therapy - therapeutic exercise"},
        "age": 52, "sex": "female", "coverage_active": True,
        "conditions": [{"code": "M54.5", "display": "Low back pain"}],
        "prior_treatments": [],
        "notes": "Low back pain, referred to outpatient physical therapy.",
    },
    {
        "id": "pt-knee", "title": "Knee MRI — approved",
        "path": "Approved", "plan_id": "PLAN_A",
        "order": {"cpt": "73721", "display": "MRI knee without contrast"},
        "age": 38, "sex": "male", "coverage_active": True,
        "conditions": [{"code": "M23.2", "display": "Derangement of meniscus"}],
        "prior_treatments": [{"type": "conservative_treatment",
                              "description": "6 weeks NSAIDs and physical therapy, no improvement"}],
        "notes": "Persistent knee pain and locking despite conservative management.",
    },
    {
        "id": "pt-brain", "title": "Brain MRI — non-covered benefit",
        "path": "Human review (coverage)", "plan_id": "PLAN_B",
        "order": {"cpt": "70551", "display": "MRI brain without contrast"},
        "age": 45, "sex": "female", "coverage_active": True,
        "conditions": [{"code": "R51.9", "display": "Headache"}],
        "prior_treatments": [],
        "notes": "Chronic daily headaches, evaluate for intracranial cause.",
    },
    {
        "id": "pt-deny", "title": "Knee MRI — insufficient evidence",
        "path": "Denied → appeal → human review", "plan_id": "PLAN_A",
        "order": {"cpt": "73721", "display": "MRI knee without contrast"},
        "age": 29, "sex": "male", "coverage_active": True,
        "conditions": [{"code": "Z00.00", "display": "General adult medical exam"}],
        "prior_treatments": [],
        "notes": "Routine visit; patient requests a knee MRI. No documented knee pathology.",
    },
    {
        "id": "pt-sleep", "title": "Sleep study — missing documentation",
        "path": "Needs info → human review", "plan_id": "PLAN_A",
        "order": {"cpt": "95810", "display": "Polysomnography (sleep study)"},
        "age": 61, "sex": "male", "coverage_active": True,
        "conditions": [{"code": "G47.33", "display": "Obstructive sleep apnea"}],
        "prior_treatments": [],
        "notes": "Suspected OSA: loud snoring, witnessed apneas, daytime somnolence.",
    },
]
CASES_BY_ID = {c["id"]: c for c in CASES}

# Prerecorded faithful runs (generated from this exact pipeline) — served as a fallback so the
# page always shows a full pipeline even when the live NIM key/quota is unavailable.
try:
    with open(os.path.join(os.path.dirname(__file__), "pa_samples.json")) as _f:
        SAMPLES = json.load(_f)
except Exception:
    SAMPLES = {}


# --- compliance: Safe-Harbor redaction (from src/compliance/redact.py) ------
_PATTERNS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DATE]"),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "[DATE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"https?://\S+"), "[URL]"),
    (re.compile(r"\bMRN[:#]?\s*\w+\b", re.I), "[MRN]"),
]


def _scrub(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def _age_band(age: int) -> str:
    if age < 18:
        return "0-17"
    if age < 40:
        return "18-39"
    if age < 65:
        return "40-64"
    return "65+"


def redact_case(case: dict) -> dict:
    """De-identified view the agents put in prompts (clinical codes retained, identifiers not)."""
    return {
        "subject": f"PT-{abs(hash(case['id'])) % 10000:04d}",
        "age_band": _age_band(case["age"]),
        "sex": case["sex"],
        "plan_id": case["plan_id"],
        "order": case["order"],
        "diagnoses": [c["code"] for c in case["conditions"]],
        "prior_treatment_types": [t["type"] for t in case["prior_treatments"]],
        "notes": _scrub(case["notes"]),
    }


# --- LLM: stdlib HTTPS to NIM (OpenAI-compatible), JSON with reject+retry ----
class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def llm_json(system: str, user: str, required_keys: list[str]) -> dict:
    """Return a dict with required_keys, retrying on invalid output (mirrors structured.extract)."""
    if not API_KEY:
        raise LLMError("NVIDIA_API_KEY is not configured on the server.")
    body = json.dumps({
        "model": MODEL, "temperature": 0.0, "max_tokens": 900,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    last = None
    for _ in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/chat/completions", data=body,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=28) as resp:
                payload = json.loads(resp.read().decode())
            content = payload["choices"][0]["message"]["content"]
            out = _extract_json(content)
            if all(k in out for k in required_keys):
                return out
            last = f"missing keys (got {list(out)})"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"          # never surface the key/body
        except Exception as e:               # bad JSON / transport / schema
            last = str(e)
    raise LLMError(f"structured output failed after {MAX_RETRIES} retries: {last}")


# --- pipeline state + audit trail -------------------------------------------
def _log(state: dict, agent: str, message: str) -> None:
    trail = state["audit_log"]
    trail.append(f"[{len(trail) + 1:02d}] {agent}: {message}")


def _step(state: dict, agent: str, status: str, detail: str) -> None:
    """Structured record for the UI stepper (status: ok|approved|denied|needs_info|review|skip)."""
    state["steps"].append({"agent": agent, "status": status, "detail": detail})


def _requires_pa(plan_id: str, cpt: str) -> bool:
    return cpt in PA_REQUIRED.get(plan_id, [])


def _is_covered(plan_id: str, cpt: str) -> bool:
    return cpt in (PLANS.get(plan_id, {}).get("covered_cpt") or [])


def _guard(codes: list) -> list:
    return [c for c in codes if c in KNOWN_ICD10]


# --- agents (faithful ports; deterministic decisions stay deterministic) -----
def agent_checker(state: dict) -> None:
    case = state["case"]
    cpt = case["order"]["cpt"]
    needs = _requires_pa(case["plan_id"], cpt)
    state["needs_pa"] = needs                       # rule table is authoritative
    if needs:
        _log(state, "Checker", f"CPT {cpt} under {case['plan_id']} requires prior authorization.")
        _step(state, "Checker", "ok", "Prior authorization is required for this order.")
    else:
        state["status"] = "done"
        _log(state, "Checker", f"CPT {cpt} under {case['plan_id']} does not require PA -> auto-cleared.")
        _step(state, "Checker", "approved", "No prior authorization required — auto-cleared.")


def agent_verifier(state: dict) -> None:
    case = state["case"]
    if not case["coverage_active"]:
        state["coverage_ok"] = False
        _log(state, "Verifier", "Member coverage is not active.")
        _step(state, "Verifier", "review", "Coverage inactive — routed to human review.")
        state["status"] = "human_review"
        return
    covered = _is_covered(case["plan_id"], case["order"]["cpt"])
    state["coverage_ok"] = covered
    if covered:
        _log(state, "Verifier", "Coverage active and procedure is a covered benefit.")
        _step(state, "Verifier", "ok", "Coverage active; procedure is a covered benefit.")
    else:
        plan = PLANS[case["plan_id"]]["name"]
        _log(state, "Verifier",
             f"Procedure {case['order']['cpt']} is a non-covered benefit under {case['plan_id']}.")
        _step(state, "Verifier", "review",
              f"Non-covered benefit under {plan} — routed to human review.")
        state["status"] = "human_review"


_ASSEMBLER_SYS = ("You are a clinical documentation specialist assembling a prior-authorization "
                  "packet. Use ONLY facts present in the patient case. Do NOT fabricate diagnoses "
                  "or treatments. Respond ONLY with a JSON object.")


def agent_assembler(state: dict) -> None:
    case = state["case"]
    loop_note = ""
    if state.get("denial_reason"):
        loop_note = ("\nThis is a re-submission. The previous packet was rejected because: "
                     f"\"{state['denial_reason']}\". Include that missing evidence only if it "
                     "genuinely exists in the case.")
    user = (
        f"Patient case (JSON):\n{json.dumps(redact_case(case), indent=2)}\n\n"
        f"Requested procedure: CPT {case['order']['cpt']} ({case['order']['display']}).{loop_note}\n\n"
        'Return JSON: {"diagnosis_codes": [ICD-10 codes FROM THE CASE that justify the order], '
        '"prior_treatments": [documented prior-treatment types, e.g. "conservative_treatment"], '
        '"clinical_justification": "2-4 sentence medical-necessity narrative grounded in the case", '
        '"attachments": [names of supporting documents]}')
    try:
        out = llm_json(_ASSEMBLER_SYS, user,
                       ["diagnosis_codes", "prior_treatments", "clinical_justification"])
    except LLMError as e:
        state["status"] = "human_review"
        _log(state, "Assembler", f"Could not assemble a valid packet ({e}) -> human review.")
        _step(state, "Assembler", "review", "Packet assembly failed — routed to human review.")
        raise
    dx_raw = [str(c) for c in out.get("diagnosis_codes", [])]
    dx = _guard(dx_raw)
    dropped = [c for c in dx_raw if c not in dx]
    if dropped:
        _log(state, "Assembler", f"Hallucination guard: dropped unrecognised code(s) {dropped}.")
    packet = state.get("packet") or {}
    packet.update({
        "patient_id": redact_case(case)["subject"],
        "order": case["order"],
        "diagnosis_codes": dx,
        "prior_treatments": [str(t) for t in out.get("prior_treatments", [])],
        "clinical_justification": out.get("clinical_justification", ""),
        "attachments": [str(a) for a in out.get("attachments", [])],
    })
    state["packet"] = packet
    _log(state, "Assembler",
         f"Built packet: dx={packet['diagnosis_codes']}, prior_tx={packet['prior_treatments']}, "
         f"{len(packet['attachments'])} attachment(s).")
    detail = f"Packet built — diagnoses {packet['diagnosis_codes'] or '[none]'}, "
    detail += f"prior treatments {packet['prior_treatments'] or '[none]'}."
    if dropped:
        detail += f" Guard dropped invented code(s) {dropped}."
    _step(state, "Assembler", "ok", detail)


def _payer_decide(packet: dict) -> dict:
    crit = NECESSITY.get(packet["order"]["cpt"])
    if not crit:
        return {"outcome": "DENIED",
                "reason": f"No medical-necessity policy on file for CPT {packet['order']['cpt']}."}
    req_dx = set(crit["required_diagnoses"])
    req_tx = set(crit["required_prior_treatments"])
    have_dx = set(packet["diagnosis_codes"])
    have_tx = set(packet["prior_treatments"])
    if req_dx and not (req_dx & have_dx):
        return {"outcome": "DENIED",
                "reason": ("Submitted diagnosis codes do not establish medical necessity for "
                           f"{crit['display']}. Need one of: {sorted(req_dx)}.")}
    missing_tx = sorted(req_tx - have_tx)
    if missing_tx:
        return {"outcome": "NEEDS_INFO",
                "reason": f"Diagnosis supports the request, but required documentation is missing: {missing_tx}."}
    if not packet["clinical_justification"].strip():
        return {"outcome": "NEEDS_INFO", "reason": "Clinical justification narrative is blank."}
    return {"outcome": "APPROVED",
            "reason": f"All medical-necessity criteria met for {crit['display']}."}


def agent_submitter(state: dict) -> str:
    decision = _payer_decide(state["packet"])
    state["decision"] = decision
    outcome = decision["outcome"]
    if outcome == "APPROVED":
        state["denial_reason"] = None
        state["status"] = "done"
        _log(state, "Submitter", f"Payer decision: APPROVED. {decision['reason']}")
        _step(state, "Submitter", "approved", f"Payer APPROVED. {decision['reason']}")
        return "APPROVED"
    state["denial_reason"] = decision["reason"]
    if outcome == "NEEDS_INFO":
        state["needs_info_loops"] += 1
        capped = state["needs_info_loops"] > MAX_NEEDS_INFO_LOOPS
    else:
        state["appeal_loops"] += 1
        capped = state["appeal_loops"] > MAX_APPEAL_LOOPS
    _log(state, "Submitter", f"Payer decision: {outcome}. {decision['reason']}")
    _step(state, "Submitter", "needs_info" if outcome == "NEEDS_INFO" else "denied",
          f"Payer {outcome}. {decision['reason']}")
    if capped:
        state["status"] = "human_review"
        _log(state, "Orchestrator", f"{outcome} loop cap reached -> routing to human review.")
        _step(state, "Orchestrator", "review",
              f"{outcome} retry cap reached — escalated to a human reviewer.")
    return outcome


_APPEALER_SYS = ("You are a physician-advisor drafting an appeal of a denied prior authorization. "
                 "Use ONLY facts present in the patient case. If the case genuinely lacks the "
                 "required evidence, write an honest letter and add nothing you cannot support. "
                 "Respond ONLY with a JSON object.")


def agent_appealer(state: dict) -> None:
    case = state["case"]
    packet = state["packet"]
    user = (
        f"Patient case (JSON):\n{json.dumps(redact_case(case), indent=2)}\n\n"
        f"Denied packet diagnosis codes: {packet['diagnosis_codes']}\n"
        f"Denied packet prior treatments: {packet['prior_treatments']}\n"
        f"Payer denial reason: \"{state.get('denial_reason', '')}\"\n\n"
        'Return JSON: {"appeal_letter": "formal appeal addressing the denial reason", '
        '"added_diagnosis_codes": [additional ICD-10 codes FROM THE CASE that rebut the denial], '
        '"added_prior_treatments": [additional documented prior treatments], '
        '"updated_justification": "strengthened justification grounded in the case"}')
    try:
        out = llm_json(_APPEALER_SYS, user, ["appeal_letter"])
    except LLMError as e:
        state["status"] = "human_review"
        _log(state, "Appealer", f"Could not draft a valid appeal ({e}) -> human review.")
        _step(state, "Appealer", "review", "Appeal drafting failed — routed to human review.")
        raise
    added_raw = [str(c) for c in out.get("added_diagnosis_codes", [])]
    added_dx = _guard(added_raw)
    dropped = [c for c in added_raw if c not in added_dx]
    if dropped:
        _log(state, "Appealer", f"Hallucination guard: dropped unrecognised code(s) {dropped}.")
    packet["diagnosis_codes"] = sorted(set(packet["diagnosis_codes"]) | set(added_dx))
    packet["prior_treatments"] = sorted(
        set(packet["prior_treatments"]) | {str(t) for t in out.get("added_prior_treatments", [])})
    if out.get("updated_justification", "").strip():
        packet["clinical_justification"] = out["updated_justification"]
    packet["appeal_letter"] = out.get("appeal_letter", "")
    state["packet"] = packet
    _log(state, "Appealer", f"Drafted appeal; added dx={added_dx}.")
    honest = " (no new evidence found in the record)" if not added_dx else ""
    _step(state, "Appealer", "ok", f"Appeal drafted and resubmitted{honest}.")


# --- plain-English rationale (from src/governance/explain.py) ----------------
def explain(state: dict) -> str:
    case = state["case"]
    lines = [f"Prior-authorization rationale for order {case['order']['cpt']} "
             f"({case['order']['display']}) under plan {case['plan_id']}:"]
    if state.get("needs_pa") is False:
        lines.append("- This procedure does not require prior authorization, so it was "
                     "auto-cleared. No further review needed.")
        return "\n".join(lines)
    lines.append("- Prior authorization IS required for this procedure under the plan.")
    if state.get("coverage_ok") is False:
        lines.append("- Coverage check failed (inactive coverage or non-covered benefit), so the "
                     "request was routed to a human reviewer.")
        return "\n".join(lines)
    lines.append("- Coverage is active and the procedure is a covered benefit.")
    decision = state.get("decision")
    outcome = decision["outcome"] if decision else None
    status = state.get("status")
    if decision:
        lines.append(f"- Payer decision: {outcome} — {decision['reason']}")
    revisions = state.get("needs_info_loops", 0)
    if status == "human_review" and outcome == "NEEDS_INFO":
        revisions -= 1
    if revisions:
        lines.append(f"- The packet was revised {revisions} time(s) to add requested documentation.")
    appeals = state.get("appeal_loops", 0)
    if status == "human_review" and outcome == "DENIED":
        appeals -= 1
    if appeals:
        lines.append(f"- {appeals} appeal(s) were drafted and resubmitted.")
    if status == "human_review":
        lines.append("- OUTCOME: escalated to a human reviewer (no automated denial is final).")
    elif status == "done" and outcome == "APPROVED":
        lines.append("- OUTCOME: approved and complete.")
    return "\n".join(lines)


# --- orchestrator (mirrors src/graph.py edges + loop caps) -------------------
def run_case(case: dict) -> dict:
    state = {"case": case, "needs_pa": None, "coverage_ok": None, "packet": None,
             "decision": None, "denial_reason": None, "needs_info_loops": 0, "appeal_loops": 0,
             "audit_log": [], "steps": [], "status": "running"}
    _log(state, "Intake", "Consent + lawful basis present (purpose=prior_authorization).")

    agent_checker(state)
    if state["status"] == "done" or not state["needs_pa"]:
        return _finalize(state)

    agent_verifier(state)
    if state["status"] == "human_review" or not state["coverage_ok"]:
        return _finalize(state)

    # assemble -> submit, with needs-info / appeal loops (caps mirror the real graph)
    guard = 0
    while guard < 8:
        guard += 1
        try:
            agent_assembler(state)
        except LLMError:
            return _finalize(state)
        outcome = agent_submitter(state)
        if outcome == "APPROVED" or state["status"] == "human_review":
            return _finalize(state)
        if outcome == "DENIED":
            try:
                agent_appealer(state)
            except LLMError:
                return _finalize(state)
            # appealer revised the packet; resubmit
            outcome = agent_submitter(state)
            if outcome == "APPROVED" or state["status"] == "human_review":
                return _finalize(state)
        # NEEDS_INFO (or post-appeal DENIED not capped) -> loop back to assembler
    state["status"] = "human_review"
    return _finalize(state)


def _finalize(state: dict) -> dict:
    if state["status"] == "running":
        state["status"] = "done"
    decision = state.get("decision")
    return {
        "case": {"id": state["case"]["id"], "title": state["case"]["title"],
                 "plan_id": state["case"]["plan_id"], "order": state["case"]["order"]},
        "needs_pa": state.get("needs_pa"),
        "coverage_ok": state.get("coverage_ok"),
        "decision": decision,
        "status": state["status"],
        "steps": state["steps"],
        "audit_log": state["audit_log"],
        "rationale": explain(state),
        "appeal_letter": (state.get("packet") or {}).get("appeal_letter"),
        "packet": state.get("packet"),
        "redacted_view": redact_case(state["case"]),
        "model": MODEL,
    }


# --- HTTP handler -----------------------------------------------------------
class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {
            "live": bool(API_KEY),
            "has_samples": bool(SAMPLES),
            "model": MODEL,
            "cases": [{"id": c["id"], "title": c["title"], "path": c["path"],
                       "plan": PLANS[c["plan_id"]]["name"], "plan_id": c["plan_id"],
                       "order": c["order"], "notes": c["notes"],
                       "diagnoses": [d["code"] for d in c["conditions"]],
                       "prior_treatments": [t["type"] for t in c["prior_treatments"]]}
                      for c in CASES],
            "agents": ["Checker", "Verifier", "Assembler", "Submitter", "Appealer"],
            "note": "Synthetic data only — no PHI. The payer decision is deterministic; the LLM only reasons, extracts, and drafts.",
        })

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
        except Exception:
            return self._send(400, {"error": "Invalid JSON body."})
        case_id = body.get("case_id")
        case = CASES_BY_ID.get(case_id)
        if not case:
            return self._send(400, {"error": "Unknown case_id. Pick one of the listed cases."})

        def _sample(reason: str):
            s = dict(SAMPLES[case_id])
            s["sample"] = True
            s["sample_reason"] = reason
            return s

        # No key configured -> serve the prerecorded run so the page still shows a full pipeline.
        if not API_KEY:
            if case_id in SAMPLES:
                return self._send(200, _sample("Prerecorded example — live LLM not configured."))
            return self._send(503, {
                "error": "The live agent is not configured. Set NVIDIA_API_KEY in the Vercel "
                         "project environment variables to enable it."})

        t0 = time.time()
        try:
            result = run_case(dict(case))
        except LLMError:
            if case_id in SAMPLES:  # key set but backend/quota failed -> graceful fallback
                return self._send(200, _sample("Prerecorded example — live LLM was unavailable."))
            return self._send(502, {"error": "LLM backend unavailable and no sample on file."})
        except Exception as e:
            return self._send(500, {"error": f"Pipeline error: {e}"})
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        self._send(200, result)
