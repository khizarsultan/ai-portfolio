"use client";
// Model Dashboard + Explainability (XAI). Ports the Streamlit model_view:
// live predict + local SHAP + what-if/ICE + counterfactual + global SHAP +
// threshold-aware performance + ops + drift. Threshold slider recomputes
// client-side from the precomputed sweep; the free-form predict still calls
// the serverless /api/diabetes.
import { useState } from "react";
import { Card, Label, TextInput, Select, RunButton, ErrorNote, DevHint, Bars, SignedBars, postJSON } from "../ui";
import { Stat, StatusPill, LineChart, ConfusionMatrix, Histogram, Gauge, C } from "../charts";
import type { DemoData, Patient } from "./types";
import { nearestSweep } from "./types";

const SUB = ["Predict & Explain", "Performance", "Explainability", "System & Ops", "Data Drift"] as const;
type Sub = typeof SUB[number];
const WHATIF_KEYS = ["HbA1c_level", "blood_glucose_level", "bmi", "age"];

export default function ModelDash({ d }: { d: DemoData }) {
  const [sub, setSub] = useState<Sub>("Predict & Explain");
  const [thr, setThr] = useState(d.threshold_default);
  const row = nearestSweep(d.sweep, thr);
  const total = row.tp + row.fp + row.fn + row.tn;
  const cm = [[row.tn, row.fp], [row.fn, row.tp]];

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{d.model_name} — ML & MLOps Dashboard</h2>
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
          <p className="text-xs text-slate-400">Lower = catch more (higher recall); higher = fewer false alarms. Recomputed live from the held-out test set.</p>
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
              <div><div className="font-semibold tabular-nums">{(row.accuracy * 100).toFixed(1)}%</div><div className="text-slate-400">Accuracy</div></div>
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
            <p className="text-xs text-slate-400">Dashed line = prevalence ({(d.baseline * 100).toFixed(1)}%), the no-skill baseline.</p>
          </Card>
        </div>
      )}
      {sub === "Explainability" && (
        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">What drives the model, globally</h3>
          <p className="mb-3 text-xs text-slate-400">Mean absolute SHAP value per feature over a test sample — the model&apos;s overall reasoning, not one patient&apos;s.</p>
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
function PredictExplain({ d, thr }: { d: DemoData; thr: number }) {
  const [pi, setPi] = useState(0);
  const [feat, setFeat] = useState("HbA1c_level");
  const patient: Patient = d.patients[pi];
  const flag = patient.probability >= thr;
  const wi = patient.whatif[feat];
  const maxAbs = Math.max(...patient.local.map((l) => Math.abs(l.shap)));

  return (
    <div className="space-y-5">
      <LivePredict />
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Worked example — full SHAP explanation <span className="font-normal text-slate-400">(precomputed illustration)</span></h3>
          <Select value={pi} onChange={(e) => setPi(+e.target.value)} >
            {d.patients.map((p, i) => <option key={p.name} value={i}>{p.name}</option>)}
          </Select>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <div className="flex flex-col items-center">
            <Gauge value={patient.probability} threshold={thr} danger={flag} />
            <div className={`mt-2 rounded-lg px-3 py-1.5 text-sm font-semibold ${flag ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"}`}>
              {flag ? "High" : "Low"} risk — {(patient.probability * 100).toFixed(1)}% {flag ? "≥" : "<"} threshold {(thr * 100).toFixed(0)}%
            </div>
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold text-slate-500">Why (1) — SHAP: top drivers of this prediction</h4>
            <SignedBars items={patient.local.map((l) => ({ label: l.feature, value: l.shap }))} max={maxAbs} />
            <p className="mt-2 text-xs text-slate-400">Red pushes risk up, blue pushes it down.</p>
          </div>
        </div>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-semibold text-slate-500">Why (2) — What-if: how this patient&apos;s risk responds</h4>
            <Select value={feat} onChange={(e) => setFeat(e.target.value)}>
              {WHATIF_KEYS.map((k) => <option key={k} value={k}>{patient.whatif[k].label}</option>)}
            </Select>
            <div className="mt-2">
              <LineChart height={240} xLabel={wi.label} yLabel="predicted risk %"
                yDomain={[0, 100]} xDomain={[wi.curve[0][0], wi.curve[wi.curve.length - 1][0]]}
                series={[{ points: wi.curve.map(([x, y]) => [x, y * 100]), color: C.brand }]}
                hlines={[{ y: thr * 100, label: "threshold", color: C.muted }]}
                markers={[{ x: wi.current, y: patient.probability * 100, color: C.crit }]} />
            </div>
            <p className="text-xs text-slate-400">Re-scored this exact patient at each value (ICE). Dot = where they are now.</p>
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold text-slate-500">Why (3) — What would change the decision</h4>
            <p className="mb-2 text-xs text-slate-400">Smallest single change that flips the current decision (others fixed).</p>
            <ul className="space-y-1.5 text-sm">
              {WHATIF_KEYS.map((k) => {
                const w = patient.whatif[k];
                return (
                  <li key={k} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 dark:bg-slate-950/50">
                    <span className="text-slate-600 dark:text-slate-300">{w.label}</span>
                    <span className="tabular-nums text-slate-500">
                      {w.flip == null ? "no flip in range" : `${w.flip > w.current ? "≥" : "≤"} ${w.flip} (now ${w.current})`}
                    </span>
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 text-xs text-slate-400">A counterfactual: the actionable threshold for each clinical value.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ---------- live free-form predictor (serverless) ----------
type Step = { stage: string; detail: Record<string, unknown> };
type LiveRes = { probability: number; threshold: number; flag: boolean; label: string; steps: Step[]; global_importance: { feature: string; importance: number }[] };
const DEFAULTS = { gender: "Female", age: 54, bmi: 28.5, HbA1c_level: 6.2, blood_glucose_level: 140, smoking_history: "never", hypertension: 0, heart_disease: 0 };

function LivePredict() {
  const [f, setF] = useState<Record<string, string | number>>({ ...DEFAULTS });
  const [res, setRes] = useState<LiveRes | null>(null);
  const [shown, setShown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const set = (k: string, v: string | number) => { setF((s) => ({ ...s, [k]: v })); setRes(null); };
  async function run() {
    setLoading(true); setErr(""); setRes(null); setShown(0);
    try {
      const r = await postJSON<LiveRes>("/api/diabetes", f);
      setRes(r);
      r.steps.forEach((_, i) => setTimeout(() => setShown(i + 1), 90 + i * 380));  // reveal each stage in turn
    } catch (e) { setErr((e as Error).message); } finally { setLoading(false); }
  }
  return (
    <Card>
      <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Score your own patient — live model</h3>
      <p className="mb-3 text-xs text-slate-400">Runs the real serverless model on your input and shows every stage it goes through.</p>
      <div className="grid items-start gap-4 md:grid-cols-2">
        <div className="grid grid-cols-2 content-start gap-3">
          <div><Label>Gender</Label><Select value={f.gender} onChange={(e) => set("gender", e.target.value)}>{["Female", "Male", "Other"].map((o) => <option key={o}>{o}</option>)}</Select></div>
          <div><Label>Age</Label><TextInput type="number" value={f.age} onChange={(e) => set("age", +e.target.value)} /></div>
          <div><Label>BMI</Label><TextInput type="number" step={0.1} value={f.bmi} onChange={(e) => set("bmi", +e.target.value)} /></div>
          <div><Label>HbA1c (%)</Label><TextInput type="number" step={0.1} value={f.HbA1c_level} onChange={(e) => set("HbA1c_level", +e.target.value)} /></div>
          <div><Label>Blood glucose</Label><TextInput type="number" value={f.blood_glucose_level} onChange={(e) => set("blood_glucose_level", +e.target.value)} /></div>
          <div><Label>Smoking</Label><Select value={f.smoking_history} onChange={(e) => set("smoking_history", e.target.value)}>{["never", "former", "current", "ever", "not current", "unknown"].map((o) => <option key={o}>{o}</option>)}</Select></div>
          <div><Label>Hypertension</Label><Select value={f.hypertension} onChange={(e) => set("hypertension", +e.target.value)}><option value={0}>No</option><option value={1}>Yes</option></Select></div>
          <div><Label>Heart disease</Label><Select value={f.heart_disease} onChange={(e) => set("heart_disease", +e.target.value)}><option value={0}>No</option><option value={1}>Yes</option></Select></div>
          <div className="col-span-2 mt-1"><RunButton loading={loading} onClick={run}>Predict risk</RunButton></div>
          {err && <div className="col-span-2"><ErrorNote msg={err} /><DevHint /></div>}
        </div>
        <div>
          <h4 className="mb-2 text-xs font-semibold text-slate-500">Under the hood — inference pipeline</h4>
          {!res && !loading && <p className="text-sm text-slate-400">Click <strong>Predict risk</strong> to run the model and watch each stage execute.</p>}
          {loading && <p className="text-sm text-slate-400">Running the model…</p>}
          {res && <PipelineTrace res={res} shown={shown} />}
        </div>
      </div>
    </Card>
  );
}

// ---------- animated pipeline visualization ----------
const STAGE_ICONS = [
  "M4 4h12v3H4zM4 9h12v2H4zM4 13h8v2H4z",                                   // input: document lines
  "M3 6h6M13 6h4M3 14h4M11 14h6 M8 4v4 M14 12v4",                          // feature eng: sliders (drawn as lines)
  "M4 4h5v5H4zM11 4h5v5h-5zM4 11h5v5H4zM11 11h5v5h-5z",                     // preprocessing: grid
  "M6 6h8v8H6z M8 2v3 M12 2v3 M8 15v3 M12 15v3 M2 8h3 M2 12h3 M15 8h3 M15 12h3", // model: chip
  "M10 2l7 4v5c0 4-3 6-7 7-4-1-7-3-7-7V6z M7 10l2 2 4-4",                   // decision: shield check
];

function StageIcon({ i }: { i: number }) {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d={STAGE_ICONS[i] ?? STAGE_ICONS[0]} />
    </svg>
  );
}

function PipelineTrace({ res, shown }: { res: LiveRes; shown: number }) {
  const steps = res.steps;
  const total = steps.length;
  const done = shown >= total;
  const progress = total > 1 ? Math.min(1, Math.max(0, shown - 1) / (total - 1)) : 0;
  return (
    <div className="relative pl-11">
      {/* rail + animated fill */}
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
      {/* terminal verdict node */}
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
