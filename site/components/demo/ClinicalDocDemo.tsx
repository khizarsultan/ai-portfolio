"use client";
import { useEffect, useState } from "react";
import { Card, RunButton, ErrorNote, DevHint, getJSON, postJSON } from "./ui";
import ClinicalFlowGraph from "./ClinicalFlowGraph";

type CaseInfo = {
  id: string; title: string; path: string; specialty: string;
  age_band: string; sex: string; raw: string;
};
type Meta = { live: boolean; model: string; cases: CaseInfo[]; agents: string[]; note: string };
type IO = { in?: Record<string, unknown>; out?: Record<string, unknown> };
type Step = { agent: string; status: string; detail: string; io?: IO };
type Code = { system: string; code: string; rationale: string };
type Soap = { subjective: string; objective: string; assessment: string; plan: string };
type RunResult = {
  soap: Soap | null; codes: Code[] | null; flags: string[]; confidence: number | null;
  signed_off: boolean; signer: string | null; record_id: string | null;
  status: string; steps: Step[]; audit_log: string[]; rationale: string;
  redacted_view: Record<string, unknown>; model: string; elapsed_ms: number;
  sample?: boolean; sample_reason?: string;
};

const STATUS_STYLE: Record<string, { dot: string; text: string; ring: string }> = {
  ok: { dot: "bg-brand", text: "text-slate-700 dark:text-slate-200", ring: "ring-brand/30" },
  recorded: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300", ring: "ring-emerald-400/40" },
  signed: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300", ring: "ring-emerald-400/40" },
  flagged: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300", ring: "ring-amber-400/40" },
  review: { dot: "bg-orange-500", text: "text-orange-700 dark:text-orange-300", ring: "ring-orange-400/40" },
};
const SOAP_LABEL: Record<keyof Soap, string> = {
  subjective: "Subjective", objective: "Objective", assessment: "Assessment", plan: "Plan",
};

function finalVerdict(r: RunResult): { label: string; tone: "good" | "warn" | "neutral" } {
  if (r.status === "recorded") return { label: `Signed & recorded (${r.record_id})`, tone: "good" };
  if (r.status === "human_review") return { label: "Escalated to a human reviewer — nothing recorded", tone: "warn" };
  return { label: "Completed", tone: "neutral" };
}

export default function ClinicalDocDemo() {
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
    getJSON<Meta>("/api/clinical-doc")
      .then((m) => { setMeta(m); setSelected(m.cases[0]?.id); })
      .catch((e) => setMetaErr(e.message));
  }, []);

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
    setShowAudit(false); setShowRedacted(false); setOpenStep(null);
    try {
      setResult(await postJSON<RunResult>("/api/clinical-doc", { case_id: selected }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (metaErr) return (<><ErrorNote msg={metaErr} /><DevHint /></>);
  if (!meta) return <p className="text-sm text-slate-400">Loading encounters…</p>;

  const activeCase = meta.cases.find((c) => c.id === selected);
  const verdict = result ? finalVerdict(result) : null;
  const done = result && visible >= result.steps.length;

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1.15fr]">
      {/* ---- left: pick an encounter + run ---- */}
      <div className="space-y-4">
        <Card>
          <h2 className="text-sm font-semibold text-slate-500">1 · Pick a synthetic encounter</h2>
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
                  {c.specialty} · {c.sex}, {c.age_band}
                </div>
              </button>
            ))}
          </div>
        </Card>

        {activeCase && (
          <Card>
            <h2 className="text-sm font-semibold text-slate-500">2 · Encounter note (raw input)</h2>
            <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs italic text-slate-600 dark:bg-slate-950/50 dark:text-slate-300">
              {activeCase.raw}
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
              Agents draft and code live against {meta.model.split("/").pop()} — this can take 5–40 seconds.
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
            <h2 className="text-sm font-semibold text-slate-500">Architecture &amp; routing</h2>
            <p className="mt-1 text-xs text-slate-400">The agent graph; the path taken on this run is highlighted. Nothing reaches the Recorder without a clinician sign-off. Click a node to jump to its step.</p>
            <div className="mt-3">
              <ClinicalFlowGraph steps={result.steps} status={result.status} revealCount={visible}
                onPick={(agent) => {
                  const idx = result.steps.findIndex((s) => s.agent === agent);
                  if (idx >= 0) setOpenStep(idx);
                }}
              />
            </div>
          </Card>
        )}

        {result && (
          <Card>
            <h2 className="text-sm font-semibold text-slate-500">Agent pipeline</h2>
            <p className="mt-1 text-xs text-slate-400">Click a step to see what that agent received and returned.</p>
            <ol className="mt-4 space-y-2">
              {result.steps.slice(0, visible).map((s, i) => {
                const st = STATUS_STYLE[s.status] ?? STATUS_STYLE.ok;
                const hasIO = !!(s.io && (s.io.in || s.io.out));
                const open = openStep === i;
                return (
                  <li key={i}>
                    <button
                      onClick={() => hasIO && setOpenStep(open ? null : i)}
                      className={`flex w-full gap-3 rounded-lg px-2 py-1 text-left ${hasIO ? "hover:bg-slate-50 dark:hover:bg-slate-800/50" : "cursor-default"}`}
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
            {result.soap && (
              <Card>
                <h2 className="text-sm font-semibold text-slate-500">SOAP note (drafted by the agents)</h2>
                <dl className="mt-3 space-y-2 text-sm">
                  {(Object.keys(SOAP_LABEL) as (keyof Soap)[]).map((k) => (
                    <div key={k}>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{SOAP_LABEL[k]}</dt>
                      <dd className="text-slate-700 dark:text-slate-200">{asText(result.soap![k]) || "—"}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
            )}

            {result.codes && (
              <Card>
                <h2 className="text-sm font-semibold text-slate-500">Extracted codes (validated against real ICD-10 / CPT sets)</h2>
                <ul className="mt-3 space-y-2">
                  {result.codes.map((c, i) => (
                    <li key={i} className="flex gap-3 text-sm">
                      <span className={`shrink-0 rounded-md px-2 py-0.5 font-mono text-xs ${
                        c.system === "CPT"
                          ? "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300"
                          : "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"}`}>
                        {c.code}
                      </span>
                      <span className="text-slate-600 dark:text-slate-300">{asText(c.rationale)}</span>
                    </li>
                  ))}
                </ul>
                {result.flags && result.flags.length > 0 && (
                  <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
                    <strong>Validation flags:</strong>
                    <ul className="mt-1 list-disc pl-4">{result.flags.map((f, i) => <li key={i}>{f}</li>)}</ul>
                  </div>
                )}
              </Card>
            )}

            <Card>
              <h2 className="text-sm font-semibold text-slate-500">Plain-English rationale</h2>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-200">{asText(result.rationale)}</pre>
            </Card>

            <div className="flex flex-wrap gap-4 text-xs">
              <button onClick={() => setShowAudit((v) => !v)} className="text-brand hover:underline">
                {showAudit ? "Hide" : "Show"} audit trail ({result.audit_log.length})
              </button>
              <button onClick={() => setShowRedacted((v) => !v)} className="text-brand hover:underline">
                {showRedacted ? "Hide" : "Show"} redacted encounter (what the LLM sees)
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
              <p className="text-sm text-slate-500">Pick an encounter and run the agent flow.</p>
              <p className="mt-2 text-xs text-slate-400">
                Intake → SOAP Writer → Coder → Validator → Sign-off → Recorder.<br />
                Codes are validated against real code sets; nothing is recorded without a clinician sign-off.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

// Backstop: never hand a non-string to a React child.
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
