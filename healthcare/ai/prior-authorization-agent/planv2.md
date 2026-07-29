Part B — Additions (open-source LLM + compliance + governance)

These are additional requirements on top of the plan above. Implement them alongside the matching phases.

B1. LLM setup — open-source, free, local

No Claude API keys. Run an open-weight model locally with Ollama (easiest on Apple Silicon, exposes an OpenAI-compatible API so the code barely changes).

Model choice
Primary: Qwen3 (Apache 2.0 license, strong tool use and reasoning).
16 GB RAM Mac -> qwen3:8b
24 GB+ RAM Mac -> qwen3:14b (better) or qwen3:30b-a3b (MoE, only ~3B active, fast)
Fallback: llama3.1:8b if Qwen misbehaves on a task.
Keep the model name in .env (MODEL_NAME), never hardcode.
Wiring it up
Install: brew install ollama, then ollama pull qwen3:8b, then ollama serve.
Use langchain-ollama's ChatOllama (points at http://localhost:11434).
Replace any ChatAnthropic(...) the generated code uses with a single get_llm() factory in src/llm/client.py that reads config and returns ChatOllama. All agents import from there — one place to swap models later.
Reliability note (important for small open models)

Small local models are less reliable at native JSON tool calling than Claude. So:

Do NOT rely on the LLM to make the final approve/deny decision — the mock payer stays deterministic (already in the plan). The LLM only reasons, extracts, and drafts.
For every agent that returns structured data, use .with_structured_output(PydanticModel) or prompt for strict JSON + validate with Pydantic. Reject + retry (max 2) on invalid output.
Keep prompts short and explicit; give one clear example per agent.
Alternative if the Mac struggles
Hugging Face Inference Providers free tier (rate-limited) via an OpenAI-compatible client — good for quick tests. Same get_llm() factory, different base URL.
If you go this route, PHI-style fields MUST be redacted before the call (see B2), since data would leave the machine. Local Ollama avoids this entirely.
New files
src/llm/
├── client.py          # get_llm() factory (ChatOllama)
└── structured.py       # helper: prompt -> validated Pydantic (retry on bad JSON)
B2. Compliance & data protection (HIPAA / GDPR patterns)

We use synthetic data, so this is not "certified compliant" — the goal is to demonstrate the controls a real system needs. Treat Synthea data as if it were real PHI. State this clearly in the README.

Implement these as a thin src/compliance/ layer:

De-identification / data minimization — a redact.py that strips the 18 HIPAA Safe Harbor identifiers (name, exact dates, MRN, address, etc.) from anything written to logs or (if ever) sent to a hosted model. Each agent receives only the fields its job needs.
Audit logging — extend the existing audit_log into an append-only, timestamped record of who/what/when for every agent action and every data access. Never mutable.
Access control (RBAC) — a simple role check: e.g. clinician, reviewer, admin. Only reviewer/admin can approve or view full packets. Enforce before any read/write.
Encryption note — document where encryption at rest/in transit would apply (DB, API). For the demo, at minimum store processed cases in a folder flagged as "encrypted-at-rest in prod" and use https for the FastAPI endpoint.
GDPR: purpose + lawful basis — tag every case with a purpose and lawful_basis field; refuse processing if missing (purpose limitation).
GDPR: retention + erasure — a delete_case(case_id) function + a documented retention policy. If FastAPI is built, expose a DELETE /case/{id} (right to erasure).
Local-model = no BAA needed — call out in the README that running the LLM locally means no PHI is disclosed to a third party, which is the cleanest compliance posture.
New files
src/compliance/
├── redact.py           # Safe Harbor identifier stripping
├── access.py           # RBAC checks
├── consent.py          # purpose / lawful basis tags + retention/erasure
└── audit.py            # append-only audit log
B3. Agent governance (the four pillars)

Build these as concrete, testable requirements — not just docs.

B3.1 Agent interoperability
Agents exchange data through versioned Pydantic contracts (a shared schema module), not loose dicts. Every handoff validates against the contract.
Use FHIR as the patient-data interchange format (already coming from Synthea) so the input side speaks a real healthcare standard.
Handoffs are idempotent — re-running a node with the same input gives the same result; safe under retries.
A single HandoffContext object carries state + audit trail between agents so no agent loses context. Document the handoff protocol in the README (this is the "agents collaborate across systems" story).
B3.2 Trust, safety & reliability
Validate every agent output against its Pydantic contract; reject + retry (max 2) then escalate to human.
Hallucination guard — check that any ICD-10/CPT code an agent emits exists in a known code list; if not, flag and escalate.
Deterministic decisions — the mock payer (rules engine) makes the call, not the LLM.
Loop caps + circuit breaker (already in graph) so it can never run away.
Regression tests + eval harness run on every change (Phase 5 eval) — this is the "ongoing validation" requirement.
B3.3 Privacy, identity & access
Each agent has its own scoped identity and permissions (least privilege): an AgentIdentity with an allow-list of tools/data it may touch. The Appealer cannot call the payer's approve path; the Checker cannot read full clinical notes it doesn't need, etc.
Tool access is policy-checked at call time, not assumed. Enforce in src/compliance/access.py.
Data minimization per agent (see B2): pass only required fields into each agent.
B3.4 Ethics, bias & transparency
Bias eval — generate a demographically diverse Synthea cohort and measure approval-rate parity across age/sex slices in eval/. Report disparities.
Human-in-the-loop gates — all denials and all escalations require human review before they're final. No fully-autonomous denial.
Transparency — every decision must produce a plain-English rationale (from the audit trail) that a human can read. Add a explain(case) function.
Escalation pathway — a clear status = human_review route with the reason attached, surfaced in the CLI/API output.
Ship a short model card / system card in the README: what it does, data used, known limits, and where humans must stay in the loop.
New files
src/governance/
├── contracts.py        # versioned Pydantic handoff schemas
├── identity.py         # AgentIdentity + per-agent permission scopes
├── guards.py           # code-existence / hallucination checks
└── explain.py          # audit trail -> human-readable rationale
eval/
└── bias_eval.py        # approval-rate parity across demographic slices
B4. Extra phase

Phase 6 — Governance & compliance layer (do after Phase 5)

Build src/compliance/ (redaction, RBAC, consent, audit).
Build src/governance/ (contracts, identity/permissions, guards, explain).
Add eval/bias_eval.py and run it.
Update README with the model card, compliance notes, and handoff protocol.
✅ Deliverable: every decision has a rationale + audit trail; bias report generated; per-agent permissions enforced; PHI-style fields redacted from logs.
B5. Extra eval metrics (add to §9)
Fairness — approval-rate parity across age/sex slices (flag gaps > a set threshold).
Reliability — % of agent outputs that pass schema validation on first try; hallucinated-code rate.
Transparency — % of decisions with a complete, human-readable rationale.
Access enforcement — tests proving each agent can't exceed its permission scope.