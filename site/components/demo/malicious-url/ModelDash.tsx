"use client";
// Model Dashboard + XAI (multiclass URL). Live classify calls /api/malicious-url
// and renders its real `stages` trace on an animated pipeline rail; worked
// examples carry precomputed local SHAP. Performance is 4-class (heatmap,
// per-class recall), plus global XAI, ops, and real drift.
import { useState } from "react";
import { Card, Label, TextInput, RunButton, ErrorNote, DevHint, Select, Bars, SignedBars, postJSON } from "../ui";
import { Stat, StatusPill, Heatmap, ColorBars, Histogram, C } from "../charts";
import type { UrlData, UrlLive, UrlStage } from "./types";
import { classColor } from "./types";

const SUB = ["Classify & Explain", "Performance", "Explainability", "System & Ops", "Data Drift"] as const;
type Sub = typeof SUB[number];

export default function ModelDash({ d }: { d: UrlData }) {
  const [sub, setSub] = useState<Sub>("Classify & Explain");
  const pc = Object.fromEntries(d.per_class.map((r) => [r.cls, r]));
  const mal = pc["malware"], phi = pc["phishing"];

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold">{d.model_name} — ML &amp; MLOps Dashboard</h2>
        <p className="text-sm text-slate-500">{d.n_test.toLocaleString()} test URLs · 4 classes — per-URL explanations and live operational health.</p>
        <div className="mt-4 grid grid-cols-3 gap-3 md:grid-cols-6">
          <Stat label="Macro-F1" value={d.metrics.macro_f1.toFixed(3)} />
          <Stat label="Macro-recall" value={d.metrics.macro_recall.toFixed(3)} />
          <Stat label="Malware recall" value={`${((mal?.recall ?? 0) * 100).toFixed(0)}%`} tone="crit" />
          <Stat label="Phishing recall" value={`${((phi?.recall ?? 0) * 100).toFixed(0)}%`} />
          <Stat label="p95 latency" value={`${d.latency.p95.toFixed(1)} ms`} />
          <Stat label="Throughput" value={`${d.latency.throughput_rps.toLocaleString()} rps`} />
        </div>
      </Card>

      <div className="flex flex-wrap gap-2">
        {SUB.map((s) => (
          <button key={s} onClick={() => setSub(s)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${sub === s ? "bg-brand text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"}`}>{s}</button>
        ))}
      </div>

      {sub === "Classify & Explain" && <ClassifyExplain d={d} />}
      {sub === "Performance" && (
        <div className="grid gap-5 md:grid-cols-2">
          <Card>
            <div className="mb-3 grid grid-cols-4 gap-2 text-center text-xs">
              <div><div className="font-semibold tabular-nums">{(d.metrics.accuracy * 100).toFixed(1)}%</div><div className="text-slate-400">Accuracy</div></div>
              <div><div className="font-semibold tabular-nums">{d.metrics.macro_f1.toFixed(3)}</div><div className="text-slate-400">Macro-F1</div></div>
              <div><div className="font-semibold tabular-nums">{d.metrics.macro_recall.toFixed(3)}</div><div className="text-slate-400">Macro-recall</div></div>
              <div><div className="font-semibold tabular-nums">{d.metrics.macro_roc_auc.toFixed(3)}</div><div className="text-slate-400">ROC-AUC</div></div>
            </div>
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Confusion matrix (row-normalized = recall on diagonal)</h3>
            <Heatmap matrix={d.confusion_norm} labels={d.classes} />
          </Card>
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Per-class recall (catch rate)</h3>
            <ColorBars items={d.per_class.map((r) => ({ label: r.cls, value: r.recall, color: classColor(r.cls) }))} />
            <h3 className="mb-2 mt-5 text-sm font-semibold text-slate-600 dark:text-slate-300">Per-class metrics</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400 dark:border-slate-800"><th className="py-1.5 pr-4">Class</th><th className="pr-4">Precision</th><th className="pr-4">Recall</th><th className="pr-4">F1</th><th>Support</th></tr></thead>
                <tbody>
                  {d.per_class.map((r) => (
                    <tr key={r.cls} className="border-b border-slate-100 dark:border-slate-900">
                      <td className="py-1.5 pr-4 font-medium">{r.cls}</td><td className="pr-4 tabular-nums">{r.precision.toFixed(3)}</td>
                      <td className="pr-4 tabular-nums">{r.recall.toFixed(3)}</td><td className="pr-4 tabular-nums">{r.f1.toFixed(3)}</td><td className="tabular-nums">{r.support.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
      {sub === "Explainability" && (
        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">What drives the model, globally</h3>
          <p className="mb-3 text-xs text-slate-400">Mean absolute SHAP value per feature, aggregated across all four classes.</p>
          <Bars items={d.global_importance.map((g) => ({ label: g.feature, value: g.importance }))} />
        </Card>
      )}
      {sub === "System & Ops" && (
        <div className="grid gap-5 md:grid-cols-3">
          <Card className="md:col-span-2">
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Latency distribution (200 requests)</h3>
            <Histogram edges={d.latency.hist.edges} counts={d.latency.hist.counts} xLabel="single-URL inference (ms)"
              markers={[{ x: d.latency.p50, color: C.good, label: "p50" }, { x: d.latency.p95, color: C.warn, label: "p95" }, { x: d.latency.p99, color: C.crit, label: "p99" }]} />
          </Card>
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">Operational health</h3>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="p50" value={`${d.latency.p50.toFixed(2)} ms`} />
              <Stat label="p95" value={`${d.latency.p95.toFixed(2)} ms`} />
              <Stat label="p99" value={`${d.latency.p99.toFixed(2)} ms`} />
              <Stat label="Throughput" value={`${(d.latency.throughput_rps / 1000).toFixed(1)}k rps`} />
              <Stat label="Process mem" value={`${d.resources.process_mem_mb.toFixed(0)} MB`} />
              <Stat label="CPU cores" value={d.resources.n_cores} />
            </div>
          </Card>
        </div>
      )}
      {sub === "Data Drift" && (
        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Data drift — Population Stability Index</h3>
          <p className="mb-3 text-xs text-slate-400">Serving URLs vs training distribution. PSI &lt; 0.1 stable · 0.1–0.25 watch · &gt; 0.25 drifted.</p>
          <div className="space-y-2">
            {d.drift.map((f) => (
              <div key={f.feature} className="flex items-center gap-3 text-sm">
                <span className="w-28 shrink-0 text-slate-500">{f.feature}</span>
                <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800"><div className="h-full rounded" style={{ width: `${Math.min(100, (f.PSI / 0.25) * 100)}%`, background: f.PSI < 0.1 ? C.good : f.PSI < 0.25 ? C.warn : C.crit }} /></div>
                <span className="w-16 shrink-0 text-right tabular-nums text-slate-400">{f.PSI.toFixed(3)}</span>
                <StatusPill status={f.status} />
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ---------- Classify & Explain ----------
function ClassifyExplain({ d }: { d: UrlData }) {
  const [ei, setEi] = useState(0);
  const ex = d.examples[ei];
  const maxAbs = Math.max(...ex.local.map((l) => Math.abs(l.shap)));
  return (
    <div className="space-y-5">
      <LiveClassify d={d} />
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Worked example — full SHAP explanation <span className="font-normal text-slate-400">(precomputed illustration)</span></h3>
          <Select value={ei} onChange={(e) => setEi(+e.target.value)}>
            {d.examples.map((e, i) => <option key={e.name} value={i}>{e.name}</option>)}
          </Select>
        </div>
        <p className="mb-3 break-all rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs text-slate-500 dark:bg-slate-950/50">{ex.url}</p>
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-semibold text-slate-500">Class probabilities — predicted <span style={{ color: classColor(ex.predicted) }} className="font-bold">{ex.predicted}</span></h4>
            <ColorBars items={d.classes.map((c) => ({ label: c, value: ex.proba[c] ?? 0, color: classColor(c), active: c === ex.predicted }))} />
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold text-slate-500">Why — top drivers toward &ldquo;{ex.predicted}&rdquo;</h4>
            <SignedBars items={ex.local.map((l) => ({ label: l.feature, value: l.shap }))} max={maxAbs} />
            <p className="mt-2 text-xs text-slate-400">Red pushes toward the class, blue pushes away (SHAP).</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ---------- live URL classifier (serverless, with real pipeline trace) ----------
const EXAMPLE_URLS: Record<string, string> = {
  benign: "https://www.wikipedia.org/wiki/Machine_learning",
  phishing: "http://paypal.com.secure-login.verify-account.ru/webscr?cmd=_login",
  malware: "http://192.168.1.45/download/setup.exe?free=1",
};

function LiveClassify({ d }: { d: UrlData }) {
  const [url, setUrl] = useState(EXAMPLE_URLS.phishing);
  const [res, setRes] = useState<UrlLive | null>(null);
  const [shown, setShown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  async function run() {
    if (!url.trim()) return;
    setLoading(true); setErr(""); setRes(null); setShown(0);
    try {
      const r = await postJSON<UrlLive>("/api/malicious-url", { url });
      setRes(r);
      r.stages.forEach((_, i) => setTimeout(() => setShown(i + 1), 90 + i * 300));
    } catch (e) { setErr((e as Error).message); } finally { setLoading(false); }
  }
  return (
    <Card>
      <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Classify a URL — live model</h3>
      <p className="mb-3 text-xs text-slate-400">Runs the real serverless classifier and shows every stage of the pipeline.</p>
      <div className="flex flex-wrap gap-2">
        {Object.entries(EXAMPLE_URLS).map(([k, u]) => (
          <button key={k} onClick={() => { setUrl(u); setRes(null); }} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300">{k} example</button>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <TextInput value={url} onChange={(e) => { setUrl(e.target.value); setRes(null); }} placeholder="Paste a URL…" />
        <RunButton loading={loading} onClick={run}>Classify</RunButton>
      </div>
      {err && <div className="mt-3"><ErrorNote msg={err} /><DevHint /></div>}
      {!res && !loading && <p className="mt-3 text-sm text-slate-400">Pick an example or paste a URL, then <strong>Classify</strong> to watch the pipeline run.</p>}
      {loading && <p className="mt-3 text-sm text-slate-400">Running the model…</p>}
      {res && <div className="mt-4"><UrlPipeline res={res} shown={shown} /></div>}
    </Card>
  );
}

const STAGE_ICONS = [
  "M4 4h12v3H4zM4 9h12v2H4zM4 13h8v2H4z", "M3 6h6M13 6h4M3 14h4M11 14h6 M8 4v4 M14 12v4",
  "M10 2l7 4v5c0 4-3 6-7 7-4-1-7-3-7-7V6z M7 10l2 2 4-4", "M4 4h5v5H4zM11 4h5v5h-5zM4 11h5v5H4zM11 11h5v5h-5z",
  "M6 6h8v8H6z M8 2v3 M12 2v3 M8 15v3 M12 15v3 M2 8h3 M2 12h3 M15 8h3 M15 12h3",
  "M3 10h3l2-5 3 10 2-5h4", "M4 10a6 6 0 1 1 12 0a6 6 0 1 1 -12 0 M10 6v4l3 2",
];

function StageIcon({ i }: { i: number }) {
  return <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><path d={STAGE_ICONS[i % STAGE_ICONS.length]} /></svg>;
}

function StageBody({ st }: { st: UrlStage }) {
  const data = st.data as unknown;
  if (st.kind === "flags") {
    const flags = data as { key: string; label: string; on: boolean }[];
    // Mixed polarity: HTTPS present is GOOD; the rest are risky WHEN present.
    return (
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {flags.map((f) => {
          const risky = f.key === "has_https" ? !f.on : f.on;      // no-HTTPS is the risky state
          const cls = risky
            ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300";
          const state = f.on ? "yes" : "no";
          return <span key={f.key} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>{risky ? "⚑" : "✓"} {f.label}: {state}</span>;
        })}
      </div>
    );
  }
  if (st.kind === "bars") {
    const bars = data as { label: string; value: number; active?: boolean }[];
    return <div className="mt-1.5"><ColorBars items={bars.map((b) => ({ label: b.label, value: b.value, color: classColor(b.label), active: b.active }))} /></div>;
  }
  if (st.kind === "importance") {
    const imp = data as { label: string; value: number }[];
    return <div className="mt-1.5"><Bars items={imp.map((x) => ({ label: x.label.replace(/^(log|num|cat|bin)__/, "").replace(/_/g, " "), value: x.value }))} /></div>;
  }
  if (st.kind === "vector") {
    const v = data as { dims: number; values: number[]; note: string };
    return (
      <div className="mt-1.5">
        <div className="flex flex-wrap gap-1">{v.values.map((x, i) => <span key={i} className="rounded bg-white px-1 py-0.5 font-mono text-[10px] text-slate-500 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">{x}</span>)}</div>
        <p className="mt-1 text-[11px] text-slate-400">{v.note}</p>
      </div>
    );
  }
  // kv
  const kv = data as { label: string; value: unknown }[];
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {kv.map((r) => (
        <span key={r.label} className="max-w-full truncate rounded bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-500 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">{r.label}: {String(r.value)}</span>
      ))}
    </div>
  );
}

function UrlPipeline({ res, shown }: { res: UrlLive; shown: number }) {
  const stages = res.stages;
  const total = stages.length;
  const done = shown >= total;
  const progress = total > 1 ? Math.min(1, Math.max(0, shown - 1) / (total - 1)) : 0;
  const mal = res.malicious;
  return (
    <div className="relative pl-11">
      <div className="absolute left-[15px] top-4 bottom-4 w-0.5 rounded bg-slate-200 dark:bg-slate-800" />
      <div className="absolute left-[15px] top-4 w-0.5 rounded bg-brand transition-[height] duration-500 ease-out" style={{ height: `calc((100% - 32px) * ${progress})` }} />
      <ol className="space-y-2.5">
        {stages.map((st, i) => {
          const on = i < shown;
          const current = i === shown - 1 && !done;
          return (
            <li key={st.key} className={`relative transition-all duration-300 ${on ? "opacity-100" : "opacity-40"}`}>
              <span className={`absolute -left-11 top-1.5 flex h-8 w-8 items-center justify-center rounded-full ring-4 ring-white transition-colors dark:ring-slate-900 ${on ? "bg-brand text-white" : "bg-slate-200 text-slate-400 dark:bg-slate-700"} ${current ? "animate-pulse" : ""}`}><StageIcon i={i} /></span>
              <div className={`rounded-xl border px-3 py-2 transition-colors ${on ? "border-brand/30 bg-brand/[0.06] dark:border-brand/40 dark:bg-brand/10" : "border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40"}`}>
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{st.title}</span>
                  <span className="text-[11px] text-slate-400">{st.summary}</span>
                </div>
                {on && <StageBody st={st} />}
              </div>
            </li>
          );
        })}
      </ol>
      <div className={`relative mt-2.5 transition-all duration-500 ${done ? "max-h-40 opacity-100" : "max-h-0 overflow-hidden opacity-0"}`}>
        <span className={`absolute -left-11 top-1.5 flex h-8 w-8 items-center justify-center rounded-full text-white ring-4 ring-white dark:ring-slate-900 ${mal ? "bg-red-500" : "bg-emerald-500"}`}>
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><path d={mal ? "M10 3v8 M10 15v.5" : "M5 10l3 3 7-7"} /></svg>
        </span>
        <div className={`rounded-xl px-4 py-3 text-center text-base font-bold ${mal ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"}`}>
          {res.predicted_class.toUpperCase()} — {((res.probabilities[res.predicted_class] ?? 0) * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}
