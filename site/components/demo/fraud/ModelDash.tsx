"use client";
// Model Dashboard + Explainability (fraud, binary imbalanced). Threshold slider
// recomputes performance client-side from the precomputed sweep; the live predictor
// calls the serverless /api/fraud on a real (anonymized) transaction and animates the
// real inference pipeline. Worked examples carry precomputed local SHAP.
import { useEffect, useState } from "react";
import { Card, Label, TextInput, Select, RunButton, ErrorNote, DevHint, Bars, SignedBars, postJSON, getJSON } from "../ui";
import { Stat, StatusPill, LineChart, ConfusionMatrix, Histogram, Gauge, C } from "../charts";
import type { FraudData, Example, FraudLive } from "./types";
import { nearestSweep } from "./types";

const SUB = ["Predict & Explain", "Performance", "Explainability", "System & Ops", "Data Drift"] as const;
type Sub = typeof SUB[number];

export default function ModelDash({ d }: { d: FraudData }) {
  const [sub, setSub] = useState<Sub>("Predict & Explain");
  const [thr, setThr] = useState(d.threshold_default);
  const row = nearestSweep(d.sweep, thr);
  const cm = [[row.tn, row.fp], [row.fn, row.tp]];

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{d.model_name} — ML &amp; MLOps Dashboard</h2>
            <p className="text-sm text-slate-500">Trained on {d.trained_on} — quality, explainability, and live operational health.</p>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-3 md:grid-cols-6">
          <Stat label="ROC-AUC" value={d.scores.ROC_AUC.toFixed(3)} />
          <Stat label="PR-AUC" value={d.scores.PR_AUC.toFixed(3)} hint="Honest metric under class imbalance." />
          <Stat label="Recall" value={`${(row.recall * 100).toFixed(0)}%`} />
          <Stat label="Precision" value={`${(row.precision * 100).toFixed(0)}%`} />
          <Stat label="p95 latency" value={`${d.latency.p95.toFixed(1)} ms`} />
          <Stat label="Throughput" value={`${d.latency.throughput_rps.toLocaleString()} rps`} />
        </div>
        <div className="mt-4">
          <Label>Decision threshold — {thr.toFixed(2)} (model-tuned {d.threshold_default.toFixed(2)})</Label>
          <input type="range" min={0.05} max={0.95} step={0.02} value={thr}
            onChange={(e) => setThr(+e.target.value)} className="w-full accent-brand" />
          <p className="text-xs text-slate-400">Lower = catch more fraud (higher recall); higher = fewer false alarms. Recomputed live from the held-out test set.</p>
        </div>
      </Card>

      <div className="flex flex-wrap gap-2">
        {SUB.map((s) => (
          <button key={s} onClick={() => setSub(s)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${sub === s ? "bg-brand text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"}`}>{s}</button>
        ))}
      </div>

      {sub === "Predict & Explain" && <PredictExplain d={d} thr={thr} />}
      {sub === "Performance" && (
        <div className="grid gap-5 md:grid-cols-2">
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Confusion @ threshold {thr.toFixed(2)}</h3>
            <ConfusionMatrix cm={cm} />
            <div className="mt-2 grid grid-cols-4 gap-2 text-center text-xs">
              <div><div className="font-semibold tabular-nums">{(row.accuracy * 100).toFixed(2)}%</div><div className="text-slate-400">Accuracy</div></div>
              <div><div className="font-semibold tabular-nums">{(row.precision * 100).toFixed(1)}%</div><div className="text-slate-400">Precision</div></div>
              <div><div className="font-semibold tabular-nums">{(row.recall * 100).toFixed(1)}%</div><div className="text-slate-400">Recall</div></div>
              <div><div className="font-semibold tabular-nums">{(row.f1 * 100).toFixed(1)}%</div><div className="text-slate-400">F1</div></div>
            </div>
          </Card>
          <Card>
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">ROC curve · AUC {d.scores.ROC_AUC.toFixed(3)}</h3>
            <LineChart xDomain={[0, 1]} yDomain={[0, 1]} xLabel="False positive rate" yLabel="True positive rate"
              series={[{ points: d.roc, color: C.brand }, { points: [[0, 0], [1, 1]], color: C.muted, dashed: true }]} />
          </Card>
          <Card className="md:col-span-2">
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Precision-Recall curve · AP {d.scores.PR_AUC.toFixed(3)}</h3>
            <LineChart xDomain={[0, 1]} yDomain={[0, 1]} xLabel="Recall" yLabel="Precision"
              series={[{ points: d.pr, color: C.aqua }]}
              hlines={[{ y: d.baseline, label: "prevalence", color: C.muted }]} />
            <p className="text-xs text-slate-400">The honest view under imbalance: dashed line = fraud prevalence ({(d.baseline * 100).toFixed(2)}%), the no-skill baseline.</p>
          </Card>
        </div>
      )}
      {sub === "Explainability" && (
        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">What drives the model, globally</h3>
          <p className="mb-3 text-xs text-slate-400">Mean absolute SHAP value per feature over a test sample. V-features are anonymized PCA signals (privacy-preserving); amount &amp; time are engineered.</p>
          <Bars items={d.global_importance.map((g) => ({ label: g.feature, value: g.importance }))} />
        </Card>
      )}
      {sub === "System & Ops" && (
        <div className="grid gap-5 md:grid-cols-3">
          <Card className="md:col-span-2">
            <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Latency distribution (200 requests)</h3>
            <Histogram edges={d.latency.hist.edges} counts={d.latency.hist.counts} xLabel="single-row inference (ms)"
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
          <p className="mb-3 text-xs text-slate-400">Serving vs training distribution. PSI &lt; 0.1 stable · 0.1–0.25 watch · &gt; 0.25 drifted (retrain).</p>
          <div className="space-y-2">
            {d.drift.map((f) => (
              <div key={f.feature} className="flex items-center gap-3 text-sm">
                <span className="w-28 shrink-0 text-slate-500">{f.feature}</span>
                <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800">
                  <div className="h-full rounded" style={{ width: `${Math.min(100, (f.PSI / 0.25) * 100)}%`, background: f.PSI < 0.1 ? C.good : f.PSI < 0.25 ? C.warn : C.crit }} />
                </div>
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

// ---------- Predict & Explain sub-view ----------
function PredictExplain({ d, thr }: { d: FraudData; thr: number }) {
  const [ei, setEi] = useState(0);
  const ex: Example = d.examples[ei];
  const flag = ex.probability >= thr;
  const maxAbs = Math.max(...ex.local.map((l) => Math.abs(l.shap)), 1e-6);

  return (
    <div className="space-y-5">
      <LivePredict thr={thr} />
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Worked example — full SHAP explanation <span className="font-normal text-slate-400">(precomputed illustration)</span></h3>
          <Select value={ei} onChange={(e) => setEi(+e.target.value)} >
            {d.examples.map((p, i) => <option key={p.name} value={i}>{p.name} · actual {p.actual ? "fraud" : "legit"}</option>)}
          </Select>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <div className="flex flex-col items-center">
            <Gauge value={ex.probability} threshold={thr} danger={flag} />
            <div className={`mt-2 rounded-lg px-3 py-1.5 text-sm font-semibold ${flag ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"}`}>
              {flag ? "Fraudulent" : "Legitimate"} — {(ex.probability * 100).toFixed(1)}% {flag ? "≥" : "<"} threshold {(thr * 100).toFixed(0)}%
            </div>
            <p className="mt-2 text-xs text-slate-400">${ex.amount.toLocaleString()} at {String(ex.hour).padStart(2, "0")}:00 · actual label: <strong>{ex.actual ? "fraud" : "legitimate"}</strong></p>
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold text-slate-500">Why — SHAP: top drivers of this prediction</h4>
            <SignedBars items={ex.local.map((l) => ({ label: l.feature, value: l.shap }))} max={maxAbs} />
            <p className="mt-2 text-xs text-slate-400">Red pushes toward fraud, blue pushes toward legitimate. V-features are anonymized PCA signals.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ---------- live free-form predictor (serverless) ----------
type Preset = { label: string; y: number; raw: Record<string, number> };
type Meta = { model_name: string; threshold: number; examples: Preset[] };

function LivePredict({ thr }: { thr: number }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [pi, setPi] = useState(0);
  const [amount, setAmount] = useState<number | "">("");
  const [res, setRes] = useState<FraudLive | null>(null);
  const [shown, setShown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    getJSON<Meta>("/api/fraud").then((m) => { setPresets(m.examples); }).catch((e) => setErr((e as Error).message));
  }, []);

  const preset = presets[pi];
  const effAmount = amount === "" ? (preset ? preset.raw.Amount : 0) : amount;

  async function run() {
    if (!preset) return;
    setLoading(true); setErr(""); setRes(null); setShown(0);
    try {
      const raw = { ...preset.raw, Amount: effAmount };
      const r = await postJSON<FraudLive>("/api/fraud", { raw });
      setRes(r);
      r.steps.forEach((_, i) => setTimeout(() => setShown(i + 1), 90 + i * 380));
    } catch (e) { setErr((e as Error).message); } finally { setLoading(false); }
  }

  return (
    <Card>
      <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Score a live transaction — real model</h3>
      <p className="mb-3 text-xs text-slate-400">The 28 V-features are anonymized PCA signals (not human-readable), so pick a real held-out transaction; you can still override the amount and re-score. Runs the real serverless model and shows every stage.</p>
      <div className="grid items-start gap-4 md:grid-cols-2">
        <div className="grid grid-cols-1 content-start gap-3">
          <div><Label>Transaction</Label>
            <Select value={pi} onChange={(e) => { setPi(+e.target.value); setAmount(""); setRes(null); }}>
              {presets.map((p, i) => <option key={i} value={i}>{p.label} (actual {p.y ? "fraud" : "legit"})</option>)}
            </Select>
          </div>
          <div><Label>Amount ($) — override</Label>
            <TextInput type="number" step={0.01} value={effAmount}
              onChange={(e) => { setAmount(e.target.value === "" ? "" : Math.max(0, +e.target.value)); setRes(null); }} />
          </div>
          <div className="mt-1"><RunButton loading={loading} onClick={run}>Predict fraud</RunButton></div>
          {err && <div><ErrorNote msg={err} /><DevHint /></div>}
        </div>
        <div>
          <h4 className="mb-2 text-xs font-semibold text-slate-500">Under the hood — inference pipeline</h4>
          {!res && !loading && <p className="text-sm text-slate-400">Click <strong>Predict fraud</strong> to run the model and watch each stage execute.</p>}
          {loading && <p className="text-sm text-slate-400">Running the model…</p>}
          {res && <PipelineTrace res={res} shown={shown} thr={thr} />}
        </div>
      </div>
    </Card>
  );
}

// ---------- animated pipeline visualization ----------
const STAGE_ICONS = [
  "M4 4h12v3H4zM4 9h12v2H4zM4 13h8v2H4z",
  "M3 6h6M13 6h4M3 14h4M11 14h6 M8 4v4 M14 12v4",
  "M4 4h5v5H4zM11 4h5v5h-5zM4 11h5v5H4zM11 11h5v5h-5z",
  "M6 6h8v8H6z M8 2v3 M12 2v3 M8 15v3 M12 15v3 M2 8h3 M2 12h3 M15 8h3 M15 12h3",
  "M10 2l7 4v5c0 4-3 6-7 7-4-1-7-3-7-7V6z M7 10l2 2 4-4",
];

function StageIcon({ i }: { i: number }) {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d={STAGE_ICONS[i] ?? STAGE_ICONS[0]} />
    </svg>
  );
}

function PipelineTrace({ res, shown }: { res: FraudLive; shown: number; thr: number }) {
  const steps = res.steps;
  const total = steps.length;
  const done = shown >= total;
  const progress = total > 1 ? Math.min(1, Math.max(0, shown - 1) / (total - 1)) : 0;
  return (
    <div className="relative pl-11">
      <div className="absolute left-[15px] top-4 bottom-4 w-0.5 rounded bg-slate-200 dark:bg-slate-800" />
      <div className="absolute left-[15px] top-4 w-0.5 rounded bg-brand transition-[height] duration-500 ease-out" style={{ height: `calc((100% - 32px) * ${progress})` }} />
      <ol className="space-y-2.5">
        {steps.map((st, i) => {
          const on = i < shown;
          const current = i === shown - 1 && !done;
          return (
            <li key={i} className={`relative transition-all duration-300 ${on ? "opacity-100" : "opacity-40"}`}>
              <span className={`absolute -left-11 top-1.5 flex h-8 w-8 items-center justify-center rounded-full ring-4 ring-white transition-colors dark:ring-slate-900 ${on ? "bg-brand text-white" : "bg-slate-200 text-slate-400 dark:bg-slate-700"} ${current ? "animate-pulse" : ""}`}>
                <StageIcon i={i} />
              </span>
              <div className={`rounded-xl border px-3 py-2 transition-colors ${on ? "border-brand/30 bg-brand/[0.06] dark:border-brand/40 dark:bg-brand/10" : "border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40"}`}>
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  <span className="text-[11px] tabular-nums text-slate-400">{i + 1}</span>{st.stage.replace(/^\d+\s*·\s*/, "")}
                </div>
                {on && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {Object.entries(st.detail).map(([k, v]) => (
                      <span key={k} className="rounded bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-500 ring-1 ring-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:ring-slate-800">
                        {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <div className={`relative mt-2.5 transition-all duration-500 ${done ? "max-h-40 opacity-100" : "max-h-0 overflow-hidden opacity-0"}`}>
        <span className={`absolute -left-11 top-1.5 flex h-8 w-8 items-center justify-center rounded-full text-white ring-4 ring-white dark:ring-slate-900 ${res.flag ? "bg-red-500" : "bg-emerald-500"}`}>
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><path d="M5 10l3 3 7-7" /></svg>
        </span>
        <div className={`rounded-xl px-4 py-3 text-center text-base font-bold ${res.flag ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"}`}>
          {res.label} — {(res.probability * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}
