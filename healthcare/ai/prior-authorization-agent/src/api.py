"""FastAPI backend for the provider console (planv3 Part C) + demo submit/erase.

Run:  ./.venv/bin/uvicorn src.api:app --reload
X-Role header sets the RBAC role (clinician | reviewer | admin); default clinician.

In production this would be served over HTTPS (encryption in transit) and the case
store encrypted at rest — see README."""
from __future__ import annotations
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.models import PatientCase
from src.graph import run_case
from src.governance.explain import explain
from src.compliance import access, consent
from src import store

app = FastAPI(title="Prior Authorization Console")

# Vite dev server origins (console runs separately in dev).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


class NoteBody(BaseModel):
    note: str = ""


class ReasonBody(BaseModel):
    reason: str = ""


def _guard(role: str, permission: str) -> None:
    try:
        access.enforce(role, permission)
    except access.AccessDenied as e:
        raise HTTPException(status_code=403, detail=str(e))


# ---- Console: queue + detail ----------------------------------------------
@app.get("/cases")
def list_cases(status: str | None = None, q: str | None = None) -> list[dict]:
    return store.list_cases(status=status, q=q)


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    rec = store.get_case(case_id)
    if not rec:
        raise HTTPException(status_code=404, detail="case not found")
    return rec


@app.post("/cases/{case_id}/run")
def run(case_id: str, x_role: str = Header(default="clinician")) -> dict:
    try:
        rec = store.run(case_id, actor_role=x_role)
    except access.AccessDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not rec:
        raise HTTPException(status_code=404, detail="case not found")
    return rec


# ---- Console: reviewer actions (role-gated) --------------------------------
@app.post("/cases/{case_id}/approve")
def approve(case_id: str, x_role: str = Header(default="clinician")) -> dict:
    _guard(x_role, "approve")
    rec = store.approve(case_id, x_role)
    if not rec:
        raise HTTPException(status_code=404, detail="case not found")
    return rec


@app.post("/cases/{case_id}/send-back")
def send_back(case_id: str, body: NoteBody, x_role: str = Header(default="clinician")) -> dict:
    rec = store.send_back(case_id, x_role, body.note)
    if not rec:
        raise HTTPException(status_code=404, detail="case not found")
    return rec


@app.post("/cases/{case_id}/escalate")
def escalate(case_id: str, body: ReasonBody, x_role: str = Header(default="clinician")) -> dict:
    _guard(x_role, "approve")   # only reviewer/admin may finalize an escalation
    rec = store.escalate(case_id, x_role, body.reason)
    if not rec:
        raise HTTPException(status_code=404, detail="case not found")
    return rec


# ---- Demo: stateless submit + right to erasure -----------------------------
@app.post("/submit")
def submit(case: PatientCase, x_role: str = Header(default="clinician")) -> dict:
    try:
        final = run_case(case, actor_role=x_role)
    except access.AccessDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    d = final.get("decision")
    resp = {
        "patient_id": case.patient_id,
        "needs_pa": final.get("needs_pa"),
        "coverage_ok": final.get("coverage_ok"),
        "decision": d.outcome.value if d else None,
        "reason": d.reason if d else None,
        "status": final.get("status"),
        "agent_steps": final.get("attempt"),
        "rationale": explain(final),
        "audit_log": final.get("audit_log"),
    }
    if final.get("packet") and access.can(x_role, "view_full_packet"):
        resp["packet"] = final["packet"].model_dump()
    return resp


@app.delete("/case/{case_id}")
def erase(case_id: str, x_role: str = Header(default="clinician")) -> dict:
    _guard(x_role, "delete")
    return {"case_id": case_id, "deleted": consent.delete_case(case_id)}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
