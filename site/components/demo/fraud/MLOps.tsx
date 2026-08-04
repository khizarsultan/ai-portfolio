"use client";
// MLOps Pipeline (fraud). Registry + drift monitor are REAL (mlflow.db + live PSI).
// The champion-vs-challenger + approval cycle is a clearly-badged illustrative
// scenario — there is no committed challenger state and the raw CSV is gone, so
// this shows what the pipeline does when drift triggers a retrain.
import { useState } from "react";
import { Card } from "../ui";
import { Stat, StatusPill, GroupedBars, C } from "../charts";
import type { FraudData } from "./types";

const STEPS = ["new txns\n(window)", "drift check\n(PSI)", "retrain\nchallenger", "evaluate\nvs champion", "manual\napproval", "production\n(serving)"];

function Flow() {
  const W = 720, H = 70, n = STEPS.length, bw = 104, gap = (W - n * bw) / (n - 1);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      {STEPS.map((s, i) => {
        const x = i * (bw + gap);
        return (
          <g key={i}>
            <rect x={x} y={12} width={bw} height={46} rx={8} fill="#eaf2fd" stroke={C.brand} className="dark:fill-slate-800" />
            {s.split("\n").map((ln, j) => <text key={j} x={x + bw / 2} y={30 + j * 13} textAnchor="middle" fontSize={9} fill="currentColor" className="text-slate-700 dark:text-slate-200">{ln}</text>)}
            {i < n - 1 && <line x1={x + bw} y1={35} x2={x + bw + gap} y2={35} stroke={C.muted} strokeWidth={1.5} markerEnd="url(#arf)" />}
          </g>
        );
      })}
      <defs><marker id="arf" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill={C.muted} /></marker></defs>
    </svg>
  );
}

const IllusBadge = () => (
  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700 dark:bg-amber-950 dark:text-amber-300">Demo scenario · illustrative</span>
);

export default function MLOps({ d }: { d: FraudData }) {
  const m = d.mlops;
  const [decision, setDecision] = useState<null | "approved" | "rejected">(null);
  const [prodV, setProdV] = useState(m.prod_version);
  const keys = ["pr_auc", "recall", "roc_auc", "precision"];
  const worst = d.drift.reduce((a, b) => (["DRIFT", "WARNING", "OK"].indexOf(b.status) < ["DRIFT", "WARNING", "OK"].indexOf(a.status) ? b : a), d.drift[0]);

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold">Fraud-Detection MLOps Pipeline</h2>
        <p className="mb-4 text-sm text-slate-500">Registry &amp; drift are live from the real pipeline; the retrain→approval cycle below is an illustrative walkthrough.</p>
        <Flow />
        <div className="mt-4 grid grid-cols-3 gap-3">
          <Stat label="Production (champion)" value={prodV ? `v${prodV}` : "—"} tone={decision === "approved" ? "good" : undefined} />
          <Stat label="Registered versions" value={m.registry.length} />
          <Stat label="Serving artifact" value="present" tone="good" />
        </div>
      </Card>

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Model registry <span className="font-normal text-slate-400">(real — MLflow)</span></h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400 dark:border-slate-800"><th className="py-2 pr-4">Version</th><th className="pr-4">Alias</th><th className="pr-4">ROC-AUC</th><th className="pr-4">PR-AUC</th><th>Model</th></tr></thead>
            <tbody>
              {m.registry.map((r) => (
                <tr key={r.version} className="border-b border-slate-100 dark:border-slate-900">
                  <td className="py-2 pr-4 font-semibold">v{r.version}</td>
                  <td className="pr-4 text-slate-500">{r.version === prodV ? "production (champion)" : r.alias}</td>
                  <td className="pr-4 tabular-nums">{r.roc_auc.toFixed(4)}</td>
                  <td className="pr-4 tabular-nums">{r.pr_auc.toFixed(4)}</td>
                  <td className="text-slate-500">{r.model_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Data-drift monitor <span className="font-normal text-slate-400">(real — serving vs training)</span></h3>
        <p className="mb-3 text-xs text-slate-400">{worst.status === "OK" ? "No significant drift — retraining not triggered (correct behavior)." : "Drift detected — a retrain would be triggered."}</p>
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

      <Card className="border-amber-200 dark:border-amber-900/60">
        <div className="mb-2 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Champion vs Challenger</h3><IllusBadge />
        </div>
        <p className="mb-3 text-xs text-slate-400">Illustrative: the current champion&apos;s metrics are real; challenger v{m.challenger.version} is a hypothetical retrain to demonstrate the promotion gate. Under class imbalance the gate is scored on PR-AUC (primary), with recall guarded.</p>
        <GroupedBars groups={["PR-AUC", "Recall", "ROC-AUC", "Precision"]}
          series={[
            { name: `Challenger v${m.challenger.version}`, color: C.brand, values: keys.map((k) => (m.challenger as Record<string, number>)[k]) },
            { name: `Champion v${m.champion.version}`, color: C.aqua, values: keys.map((k) => (m.champion as Record<string, number>)[k]) },
          ]} />
        <div className="mt-3">
          <h4 className="mb-1 text-xs font-semibold text-slate-500">Promotion gate</h4>
          <ul className="mb-2 space-y-1 text-sm text-slate-600 dark:text-slate-300">{m.gate_reasons.map((r, i) => <li key={i}>• {r}</li>)}</ul>
          <div className="rounded-lg bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">GATE PASSED → eligible for approval</div>
        </div>
      </Card>

      <Card className="border-amber-200 dark:border-amber-900/60">
        <div className="mb-2 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Manual approval gate (human-in-the-loop)</h3><IllusBadge />
        </div>
        {decision == null && (
          <>
            <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">Challenger <strong>v{m.challenger.version}</strong> passed the gate and is awaiting sign-off (current champion v{m.champion.version}).</div>
            <div className="flex gap-3">
              <button onClick={() => { setDecision("approved"); setProdV(m.challenger.version); }} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-light">Approve &amp; promote</button>
              <button onClick={() => setDecision("rejected")} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300">Reject</button>
            </div>
          </>
        )}
        {decision === "approved" && <div className="rounded-lg bg-emerald-100 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">v{m.challenger.version} promoted to PRODUCTION — it would now serve the Model Dashboard. (Illustrative.)</div>}
        {decision === "rejected" && <div className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">Challenger v{m.challenger.version} rejected — champion v{m.champion.version} stays in production.</div>}
        {decision && <button onClick={() => { setDecision(null); setProdV(m.prod_version); }} className="mt-3 text-xs text-slate-400 underline">reset scenario</button>}
      </Card>
    </div>
  );
}
