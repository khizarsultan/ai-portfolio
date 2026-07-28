"use client";
import { useEffect, useState } from "react";
import { Card, RunButton, ErrorNote, DevHint, getJSON, postJSON } from "./ui";

type CaseInfo = {
  id: string; title: string; path: string; plan: string; plan_id: string;
  order: { cpt: string; display: string }; notes: string;
  diagnoses: string[]; prior_treatments: string[];
};
type Meta = { live: boolean; has_samples: boolean; model: string; cases: CaseInfo[]; agents: string[]; note: string };
type Step = { agent: string; status: string; detail: string };
type RunResult = {
  needs_pa: boolean | null; coverage_ok: boolean | null;
  decision: { outcome: string; reason: string } | null;
  status: string; steps: Step[]; audit_log: string[]; rationale: string;
  appeal_letter: string | null; redacted_view: Record<string, unknown>;
  model: string; elapsed_ms: number; sample?: boolean; sample_reason?: string;
};

const STATUS_STYLE: Record<string, { dot: string; text: string; ring: string }> = {
  ok: { dot: "bg-brand", text: "text-slate-700 dark:text-slate-200", ring: "ring-brand/30" },
  approved: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300", ring: "ring-emerald-400/40" },
  denied: { dot: "bg-red-500", text: "text-red-700 dark:text-red-300", ring: "ring-red-400/40" },
  needs_info: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300", ring: "ring-amber-400/40" },
  review: { dot: "bg-orange-500", text: "text-orange-700 dark:text-orange-300", ring: "ring-orange-400/40" },
};

function finalVerdict(r: RunResult): { label: string; tone: "good" | "warn" | "neutral" } {
  if (r.needs_pa === false) return { label: "Auto-cleared — no prior authorization required", tone: "good" };
  if (r.status === "human_review") return { label: "Escalated to a human reviewer", tone: "warn" };
  if (r.decision?.outcome === "APPROVED") return { label: "Approved", tone: "good" };
  return { label: "Completed", tone: "neutral" };
}

export default function PaAgentDemo() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaErr, setMetaErr] = useState<string>();
  const [selected, setSelected] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [result, setResult] = useState<RunResult | null>(null);
  const [visible, setVisible] = useState(0);
  const [showAudit, setShowAudit] = useState(false);
  const [showRedacted, setShowRedacted] = useState(false);

  useEffect(() => {
    getJSON<Meta>("/api/pa-agent")
      .then((m) => { setMeta(m); setSelected(m.cases[0]?.id); })
      .catch((e) => setMetaErr(e.message));
  }, []);

  // Reveal the pipeline steps one at a time once a result arrives.
  useEffect(() => {
    if (!result) return;
    setVisible(0);
    const t = setInterval(() => {
      setVisible((v) => {
        if (v >= result.steps.length) { clearInterval(t); return v; }
        return v + 1;
      });
    }, 450);
    return () => clearInterval(t);
  }, [result]);

  async function run() {
    if (!selected) return;
    setLoading(true); setError(undefined); setResult(null);
    setShowAudit(false); setShowRedacted(false);
    try {
      setResult(await postJSON<RunResult>("/api/pa-agent", { case_id: selected }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (metaErr) return (<><ErrorNote msg={metaErr} /><DevHint /></>);
  if (!meta) return <p className="text-sm text-slate-400">Loading cases…</p>;

  const activeCase = meta.cases.find((c) => c.id === selected);
  const verdict = result ? finalVerdict(result) : null;
  const done = result && visible >= result.steps.length;

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1.15fr]">
      {/* ---- left: pick a case + run ---- */}
      <div className="space-y-4">
        <Card>
          <h2 className="text-sm font-semibold text-slate-500">1 · Pick a synthetic case</h2>
          <div className="mt-3 space-y-2">
            {meta.cases.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                  selected === c.id
                    ? "border-brand bg-brand/5 ring-1 ring-brand/30"
                    : "border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-800 dark:text-slate-100">{c.title}</span>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">{c.path}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {c.plan} · CPT {c.order.cpt} ({c.order.display})
                </div>
              </button>
            ))}
          </div>
        </Card>

        {activeCase && (
          <Card>
            <h2 className="text-sm font-semibold text-slate-500">2 · Case detail</h2>
            <dl className="mt-3 space-y-1.5 text-sm">
              <Row k="Plan" v={`${activeCase.plan} (${activeCase.plan_id})`} />
              <Row k="Order" v={`CPT ${activeCase.order.cpt} — ${activeCase.order.display}`} />
              <Row k="Diagnoses" v={activeCase.diagnoses.join(", ") || "—"} />
              <Row k="Prior treatments" v={activeCase.prior_treatments.join(", ") || "—"} />
            </dl>
            <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs italic text-slate-500 dark:bg-slate-950/50">
              {activeCase.notes}
            </p>
          </Card>
        )}

        <div>
          <RunButton loading={loading} onClick={run} disabled={!selected}>
            {loading ? "Agents running…" : "Run agent flow"}
          </RunButton>
          {!meta.live && (
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Live LLM key not set — runs replay a <strong>prerecorded example</strong> of the same pipeline.
            </p>
          )}
          {loading && (
            <p className="mt-2 text-xs text-slate-400">
              Five agents run live against {meta.model.split("/").pop()} — this can take 5–40 seconds.
            </p>
          )}
        </div>
      </div>

      {/* ---- right: pipeline + results ---- */}
      <div className="space-y-4">
        {error && <ErrorNote msg={error} />}
        {error && <DevHint />}

        {result && verdict && (
          <div
            className={`rounded-xl px-4 py-3 text-center text-lg font-bold transition ${
              verdict.tone === "good"
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                : verdict.tone === "warn"
                ? "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300"
                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
            } ${done ? "opacity-100" : "opacity-60"}`}
          >
            {done ? verdict.label : "Running pipeline…"}
          </div>
        )}

        {done && result?.sample && (
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950/50">
            {result.sample_reason || "Prerecorded example."} Structure and outcome match a real run of the pipeline.
          </p>
        )}

        {result && (
          <Card>
            <h2 className="text-sm font-semibold text-slate-500">Agent pipeline</h2>
            <ol className="mt-4 space-y-3">
              {result.steps.slice(0, visible).map((s, i) => {
                const st = STATUS_STYLE[s.status] ?? STATUS_STYLE.ok;
                return (
                  <li key={i} className="flex gap-3">
                    <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-4 ${st.dot} ${st.ring}`} />
                    <div>
                      <div className={`text-sm font-semibold ${st.text}`}>{s.agent}</div>
                      <div className="text-sm text-slate-600 dark:text-slate-300">{s.detail}</div>
                    </div>
                  </li>
                );
              })}
              {visible < result.steps.length && (
                <li className="flex gap-3">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-slate-300 dark:bg-slate-600" />
                  <div className="text-sm text-slate-400">…</div>
                </li>
              )}
            </ol>
          </Card>
        )}

        {done && result && (
          <>
            <Card>
              <h2 className="text-sm font-semibold text-slate-500">Plain-English rationale</h2>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-200">{result.rationale}</pre>
            </Card>

            {result.appeal_letter && (
              <Card>
                <h2 className="text-sm font-semibold text-slate-500">Appeal letter (drafted by the Appealer)</h2>
                <pre className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-200">{result.appeal_letter}</pre>
              </Card>
            )}

            <div className="flex flex-wrap gap-4 text-xs">
              <button onClick={() => setShowAudit((v) => !v)} className="text-brand hover:underline">
                {showAudit ? "Hide" : "Show"} audit trail ({result.audit_log.length})
              </button>
              <button onClick={() => setShowRedacted((v) => !v)} className="text-brand hover:underline">
                {showRedacted ? "Hide" : "Show"} redacted case (what the LLM sees)
              </button>
              <span className="ml-auto text-slate-400">{result.elapsed_ms} ms · {result.model.split("/").pop()}</span>
            </div>

            {showAudit && (
              <Card>
                <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {result.audit_log.join("\n")}
                </pre>
              </Card>
            )}
            {showRedacted && (
              <Card>
                <p className="mb-2 text-xs text-slate-400">
                  HIPAA Safe-Harbor de-identified view — the only data sent off-machine to the model.
                </p>
                <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {JSON.stringify(result.redacted_view, null, 2)}
                </pre>
              </Card>
            )}
          </>
        )}

        {!result && !error && (
          <Card className="flex min-h-[16rem] items-center justify-center text-center">
            <div>
              <p className="text-sm text-slate-500">Pick a case and run the agent flow.</p>
              <p className="mt-2 text-xs text-slate-400">
                Checker → Verifier → Assembler → Submitter → Appealer.<br />
                The payer decision is deterministic; the LLM only reasons, extracts, and drafts.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-32 shrink-0 text-slate-400">{k}</dt>
      <dd className="text-slate-700 dark:text-slate-200">{v}</dd>
    </div>
  );
}
