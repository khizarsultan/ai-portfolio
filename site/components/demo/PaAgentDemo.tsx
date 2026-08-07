"use client";
import { useEffect, useState } from "react";
import { Card, RunButton, ErrorNote, DevHint, EvalScores, EvalMetric, getJSON, postJSON } from "./ui";
import AgentFlowGraph from "./AgentFlowGraph";
import GovernancePanel, { type Pillar } from "./GovernancePanel";

type CaseInfo = {
  id: string; title: string; path: string; plan: string; plan_id: string;
  order: { cpt: string; display: string }; notes: string;
  diagnoses: string[]; prior_treatments: string[];
};
type Meta = { model: string; cases: CaseInfo[]; agents: string[] };
type IO = { in?: Record<string, unknown>; out?: Record<string, unknown> };
type Step = { agent: string; status: string; detail: string; io?: IO };
type RunResult = {
  needs_pa: boolean | null; coverage_ok: boolean | null;
  decision: { outcome: string; reason: string } | null;
  status: string; steps: Step[]; audit_log: string[]; rationale: string;
  appeal_letter: string | null; redacted_view: Record<string, unknown>;
  evals?: EvalMetric[]; governance?: Pillar[]; model: string; elapsed_ms: number;
};

const STATUS_STYLE: Record<string, { dot: string; text: string; ring: string }> = {
  ok: { dot: "bg-brand", text: "text-slate-700 dark:text-slate-200", ring: "ring-brand/30" },
  approved: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300", ring: "ring-emerald-400/40" },
  denied: { dot: "bg-red-500", text: "text-red-700 dark:text-red-300", ring: "ring-red-400/40" },
  needs_info: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300", ring: "ring-amber-400/40" },
  review: { dot: "bg-orange-500", text: "text-orange-700 dark:text-orange-300", ring: "ring-orange-400/40" },
};

// Colour the scenario badge by its outcome path so the list is scannable at a glance.
function pathTone(path: string): string {
  const p = path.toLowerCase();
  if (/(review|reject|deny|denied|escalat|not covered)/.test(p))
    return "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300";
  if (/(approv|record|clear|auto)/.test(p))
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300";
  return "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400";
}

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
  const [openStep, setOpenStep] = useState<number | null>(null);

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
    }, 250);
    return () => clearInterval(t);
  }, [result]);

  async function run() {
    if (!selected) return;
    setLoading(true); setError(undefined); setResult(null);
    setShowAudit(false); setShowRedacted(false); setOpenStep(null);
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
    <div className="grid gap-6 lg:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
      {/* ---- left: sticky rail — pick a case + prominent Run ---- */}
      <div className="space-y-4 self-start lg:sticky lg:top-6">
        <Card className="!p-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Choose a scenario</h2>
            <span className="text-[11px] text-slate-400">{meta.cases.length} cases · complex → simple</span>
          </div>

          <RunButton
            loading={loading}
            onClick={run}
            disabled={!selected}
            className="mt-3 w-full justify-center py-3 text-base"
          >
            {loading ? "Agents running…" : result ? "▸ Run again" : "▸ Run agent flow"}
          </RunButton>
          <p className="mt-1.5 text-center text-[11px] text-slate-400">Runs the selected scenario below · 5 agents</p>

          <div className="mt-4 space-y-1.5">
            {meta.cases.map((c, i) => {
              const active = selected === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setSelected(c.id)}
                  className={`group flex w-full items-start gap-3 rounded-xl border px-3 py-2 text-left transition ${
                    active
                      ? "border-brand bg-brand/5 ring-1 ring-brand/30"
                      : "border-slate-200 hover:border-brand/40 hover:bg-slate-50 dark:border-slate-800 dark:hover:border-slate-700 dark:hover:bg-slate-800/40"
                  }`}
                >
                  <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                    active ? "bg-brand text-white" : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                  }`}>{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{c.title}</span>
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${pathTone(c.path)}`}>{c.path}</span>
                      <span className="text-[11px] text-slate-400">CPT {c.order.cpt}</span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </Card>

        {activeCase && (
          <Card className="!p-5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Case detail</h2>
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
      </div>

      {/* ---- right: pipeline + results ---- */}
      <div className="space-y-4">
        {error && <ErrorNote msg={error} />}
        {error && <DevHint />}

        {result && verdict && (
          <div
            className={`flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-center text-lg font-bold transition ${
              verdict.tone === "good"
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                : verdict.tone === "warn"
                ? "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300"
                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
            } ${done ? "opacity-100" : "opacity-60"}`}
          >
            {done ? (
              <>
                <span aria-hidden>{verdict.tone === "good" ? "✓" : verdict.tone === "warn" ? "⚠" : "•"}</span>
                <span>{verdict.label}</span>
              </>
            ) : (
              <span className="inline-flex items-center gap-2 text-base font-semibold text-slate-500 dark:text-slate-300">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand" />
                Running pipeline…
              </span>
            )}
          </div>
        )}

        {result && (
          <div className={`grid gap-4 ${done && result.evals ? "xl:grid-cols-[minmax(0,1fr)_minmax(0,300px)]" : ""}`}>
            <Card>
              <h2 className="text-sm font-semibold text-slate-500">Architecture &amp; routing</h2>
              <p className="mt-1 text-xs text-slate-400">The agent graph; the path taken on this run is highlighted. Click a node to jump to its step.</p>
              <div className="mt-3">
                <AgentFlowGraph
                  steps={result.steps} status={result.status} decision={result.decision}
                  needsPa={result.needs_pa} coverageOk={result.coverage_ok} revealCount={visible}
                  onPick={(agent) => {
                    const idx = result.steps.findIndex((s) => s.agent === agent);
                    if (idx >= 0) setOpenStep(idx);
                  }}
                />
              </div>
            </Card>
            {done && result.evals && <EvalScores metrics={result.evals} />}
          </div>
        )}

        {result && (
          <Card>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-500">Agent pipeline</h2>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] tabular-nums text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {Math.min(visible, result.steps.length)}/{result.steps.length} steps
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">Click a step to see what that agent received and returned.</p>
            <ol className="mt-4 space-y-2">
              {result.steps.slice(0, visible).map((s, i) => {
                const st = STATUS_STYLE[s.status] ?? STATUS_STYLE.ok;
                const hasIO = !!(s.io && (s.io.in || s.io.out));
                const open = openStep === i;
                return (
                  <li key={i} className="animate-[fadeIn_0.3s_ease]">
                    <button
                      onClick={() => hasIO && setOpenStep(open ? null : i)}
                      className={`flex w-full gap-3 rounded-lg px-2 py-1.5 text-left ${hasIO ? "hover:bg-slate-50 dark:hover:bg-slate-800/50" : "cursor-default"}`}
                    >
                      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ring-4 ${st.dot} ${st.ring}`} />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-semibold ${st.text}`}>{s.agent}</span>
                          {hasIO && <span className="text-[11px] text-slate-400">{open ? "▾ hide I/O" : "▸ I/O"}</span>}
                        </div>
                        <div className="text-sm text-slate-600 dark:text-slate-300">{asText(s.detail)}</div>
                      </div>
                    </button>
                    {open && hasIO && (
                      <div className="ml-7 mt-1 grid gap-2 sm:grid-cols-2">
                        <IOBlock title="Received" data={s.io!.in} />
                        <IOBlock title="Returned" data={s.io!.out} />
                      </div>
                    )}
                  </li>
                );
              })}
              {visible < result.steps.length && (
                <li className="flex gap-3 px-2">
                  <span className="mt-1.5 h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-slate-300 dark:bg-slate-600" />
                  <div className="text-sm text-slate-400">…</div>
                </li>
              )}
            </ol>
          </Card>
        )}

        {done && result && (
          <>
            {result.governance && <GovernancePanel pillars={result.governance} />}

            <Card>
              <h2 className="text-sm font-semibold text-slate-500">Plain-English rationale</h2>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-200">{asText(result.rationale)}</pre>
            </Card>

            {result.appeal_letter && (
              <Card>
                <h2 className="text-sm font-semibold text-slate-500">Appeal letter (drafted by the Appealer)</h2>
                <pre className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-200">{asText(result.appeal_letter)}</pre>
              </Card>
            )}

            <div className="flex flex-wrap items-center gap-4 text-xs">
              <button onClick={() => setShowAudit((v) => !v)} className="text-brand hover:underline">
                {showAudit ? "Hide" : "Show"} audit trail ({result.audit_log.length})
              </button>
              <button onClick={() => setShowRedacted((v) => !v)} className="text-brand hover:underline">
                {showRedacted ? "Hide" : "Show"} redacted case (what the model sees)
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
          <Card className="flex min-h-[22rem] flex-col items-center justify-center border-dashed text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-2xl text-brand">▸</div>
            <p className="mt-4 text-sm font-medium text-slate-600 dark:text-slate-300">Pick a scenario and hit <span className="text-brand">Run agent flow</span></p>
            <p className="mt-2 max-w-sm text-xs text-slate-400">
              Watch five agents check, verify, assemble, submit and appeal — step by step.
              The payer decision is deterministic; the model only reasons, extracts, and drafts.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}

// Backstop: never hand a non-string to a React child. Flattens any dict/list a model field
// might contain (the server also coerces, this guards against anything slipping through).
function asText(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.map(asText).join("\n");
  if (typeof v === "object")
    return Object.entries(v as Record<string, unknown>)
      .map(([k, val]) => { const s = asText(val); return s.trim() ? `${k}: ${s}` : k; })
      .join("\n");
  return String(v);
}

// Small panel showing an agent's inputs or outputs (the under-the-hood I/O).
function IOBlock({ title, data }: { title: string; data?: Record<string, unknown> }) {
  const entries = data ? Object.entries(data) : [];
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{title}</div>
      {entries.length === 0 ? (
        <div className="text-xs text-slate-400">—</div>
      ) : (
        <dl className="space-y-1">
          {entries.map(([k, v]) => (
            <div key={k} className="text-xs">
              <dt className="text-slate-400">{k}</dt>
              <dd className="whitespace-pre-wrap break-words font-mono text-slate-700 dark:text-slate-200">{asText(v)}</dd>
            </div>
          ))}
        </dl>
      )}
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
