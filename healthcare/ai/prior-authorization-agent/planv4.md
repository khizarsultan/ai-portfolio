Part D — Observability, evals & transparency (Langfuse)

Implement the deferred items using Langfuse — the single observability + eval layer. This gives industry-grade agent tracking (cost, tokens, latency, errors, logs, every tool call, full per-step reasoning) plus the eval dashboards. Do NOT hand-build these views in React — instrument the agents and use Langfuse's UI, deep-linked from the app.

(Phoenix/Arize is an optional later add-on for deeper offline eval rigor. Not now.)

D1. Setup
Self-host Langfuse via its official docker-compose (Postgres + ClickHouse) for free, OR use Langfuse Cloud free tier for the demo.
Add keys to .env:
LANGFUSE_HOST=http://localhost:3000        # or cloud URL
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_ENABLED=true                        # feature flag so it can be turned off
Add the langfuse SDK + langfuse-langchain to deps.
D2. Instrumentation (tracing everything)
Attach the Langfuse CallbackHandler to the LangGraph run (one line) so every node, LLM call, and tool call is traced automatically.
Each PA case = one trace. Each agent (Checker/Verifier/Assembler/Submitter/Appealer) = a span. Each LLM/tool call = a nested observation.
Capture per step: inputs, outputs, token counts + cost (map the NVIDIA model so cost is computed), latency, and any errors/exceptions.
Use sessions to group the full lifecycle of a case across appeal/needs-info loops, so attempt 1 vs attempt 2 are visible in one place.
Tag traces with metadata: case_id, procedure_code, plan_id, role, decision.
D3. Custom scores & flags (feeds the dashboards + transparency)

Push these to Langfuse as scores/tags on each trace:

Decision correctness (vs expected label) — for accuracy.
Hallucination-guard flag — when the code-existence guard (§B3.2) rejects an ICD-10/CPT.
Schema-valid on first try (yes/no) — for reliability.
Escalated / human_review (yes/no).
Demographic slice (age band, sex) — for fairness/bias analysis.
D4. Eval dashboards (accuracy, fairness/bias, reliability)
Turn eval/test_cases.json into a Langfuse dataset.
Run the agent system as a Langfuse experiment over the dataset; attach the scores in D3.
Build Langfuse dashboards for:
Accuracy — final-decision + PA-needed correctness, appeal recovery rate.
Fairness/bias — approval-rate parity across demographic slices (from bias_eval.py).
Reliability — schema-valid rate, hallucinated-code rate, avg steps/case, error rate.
Cost — cost per case, per agent, per model.
Wire eval/run_eval.py and eval/bias_eval.py to log results as experiment runs so the dashboards update each run (this is the "ongoing validation" story).
D5. Deep transparency views (use Langfuse UI, link from app)
Langfuse's trace tree already provides: full per-step agent reasoning, which tool was called with inputs/outputs, timings, cost, and an audit-trail explorer per case.
Side-by-side appeal diffs — because loops are in one session, the original packet vs the appealed packet are both captured; use the session view to compare attempts. (If a tighter diff is wanted later, add a small custom view; not required now.)
From the React Case detail screen, add a "View full trace" link that deep-links to the Langfuse trace for that case_id. Keep the React UI focused on the workflow; Langfuse is the debugging/transparency surface.
D6. Compliance note
Enable Langfuse PII masking so patient-style fields are redacted in traces (reuse the Safe Harbor redaction from §B2).
Data is synthetic, so tracing is fine here. For real PHI you'd self-host Langfuse so trace data stays in your own infra (state this in the README/model card).
D7. Phase

Phase 8 — Observability & evals (Langfuse) — after Phase 7.

✅ Deliverable: every case fully traced (cost, tokens, latency, errors, tool calls, per-step reasoning); custom scores logged; accuracy/fairness/reliability/cost dashboards live; "View full trace" deep-link from the Case detail screen; PII masking on.