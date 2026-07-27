Part C — Frontend (build now)

An internal provider-side console (doctor's office billing / PA team) — not a patient app. Build the working app now. Agent-evaluation dashboards and the deep transparency/reasoning views are deferred to a later phase (see "Deferred" below) — do not build them yet.

C1. Users / roles
PA specialist / admin — primary user; runs the queue.
Clinician — signs off on the assembled packet.
Reviewer / supervisor — approves denials and handles escalations.

For now, a simple role switch (dropdown or config) is fine — no full auth system yet.

C2. Stack
React + Vite + Tailwind.
Talks to the existing FastAPI backend over REST.
State: React Query (or simple fetch hooks). No global state library needed.
Keep it clean and status-driven; this is a console, not a marketing site.
C3. Screens (build these 3)
1. Queue (home)
Table of PA requests: patient, procedure, status badge, turnaround time, last updated.
Status values: needs_pa, in_progress, approved, denied, human_review.
Filters (by status) + search (patient / procedure).
Row click -> Case detail.
2. Case detail (the main screen)
Patient + order summary at top.
Status stepper — a simple horizontal stepper showing where the case is in the flow (Checker → Verifier → Assembler → Submitter → Appealer), with the current step highlighted. Keep it simple: step name + done/current/pending state. (Rich per-step reasoning is deferred.)
Decision panel — final decision + the plain-English rationale string from the backend.
Action bar (role-gated): Approve, Send back (with a note field), Escalate. All denials/escalations require a reviewer action before final.
3. Review view
Same table, filtered to human_review, with the escalation reason shown inline.
C4. Backend endpoints needed (add to FastAPI if missing)
GET  /cases?status=&q=          # list for queue
GET  /cases/{id}               # detail: patient, order, status, current_step, decision, rationale
POST /cases/{id}/approve       # reviewer action
POST /cases/{id}/send-back     # body: { note }
POST /cases/{id}/escalate      # body: { reason }
POST /cases/{id}/run           # (optional) trigger the agent flow for a case

Return JSON that maps directly to the screens above. Reuse existing state/models.

C5. Design principles
Status over decoration; clear badges and states.
Human controls prominent on denials and escalations.
Responsive enough for a laptop; desktop-first is fine.
C6. Deferred (do NOT build yet — later phase)
Agent-evaluation dashboards (accuracy, fairness/bias, reliability metrics).
Deep transparency views: full per-step agent reasoning, audit-trail explorer, hallucination-guard flags, side-by-side appeal diffs.
Full authentication / SSO. Keep the data model ready for these (the backend already logs the audit trail), but the UI for them comes later.
C7. Phase

Phase 7 — Frontend (console) — after Phase 6.

✅ Deliverable: React console with Queue, Case detail (summary + simple stepper + decision + actions), and Review view, wired to FastAPI. Reviewer can approve / send back / escalate