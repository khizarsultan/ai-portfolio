"use client";
// MLOps Pipeline — ports the Streamlit mlops_view: registry, drift-triggered
// flow, champion vs challenger, and the manual approval gate + audit trail.
// All values are the real pipeline's recorded state (precomputed JSON); the
// approve/reject buttons reveal the decision that was actually recorded.
import { useState } from "react";
import { Card } from "../ui";
import { Stat, StatusPill, GroupedBars, C } from "../charts";
import type { DemoData } from "./types";

const STEPS = ["new data\n(window)", "drift check\n(PSI + Evidently)", "retrain\nchallenger", "evaluate\nvs champion", "manual\napproval", "production\n(serving)"];

function Flow() {
  const W = 720, H = 70, n = STEPS.length, bw = 104, gap = (W - n * bw) / (n - 1);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      {STEPS.map((s, i) => {
        const x = i * (bw + gap);
        return (
          <g key={i}>
            <rect x={x} y={12} width={bw} height={46} rx={8} fill="#eaf2fd" stroke={C.brand} className="dark:fill-slate-800" />
            {s.split("\n").map((ln, j) => (
              <text key={j} x={x + bw / 2} y={30 + j * 13} textAnchor="middle" fontSize={9} fill="currentColor" className="text-slate-700 dark:text-slate-200">{ln}</text>
            ))}
            {i < n - 1 && <line x1={x + bw} y1={35} x2={x + bw + gap} y2={35} stroke={C.muted} strokeWidth={1.5} markerEnd="url(#ar)" />}
          </g>
        );
      })}
      <defs><marker id="ar" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill={C.muted} /></marker></defs>
    </svg>
  );
}

export default function MLOps({ d }: { d: DemoData }) {
  const m = d.mlops;
  const [decision, setDecision] = useState<null | "approved" | "rejected">(null);
  const [prodV, setProdV] = useState(m.prod_version);
  const [log, setLog] = useState(m.approvals);
  const keys = ["roc_auc", "pr_auc", "recall", "precision", "f1"];
  const dt = m.drift_trigger;

  function approve() {
    setDecision("approved");
    setProdV(m.challenger_version);
    const now = new Date().toISOString().slice(0, 16).replace("T", " ");
    setLog([...m.approvals, { timestamp: now, challenger_version: m.challenger_version ?? 0,
      previous_champion: m.prod_version ?? 0, approver: "you (demo reviewer)",
      reason: "Approved in demo console — passed gate, drift-triggered.", action: "promoted_to_production" }]);
  }
  function reject() { setDecision("rejected"); }

  const aliasFor = (v: number) =>
    v === prodV ? "production (champion)"
    : decision === "approved" && v === m.prod_version ? "archived (previous champion)"
    : v === m.challenger_version ? "challenger (pending approval)" : "registered";

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold">Healthcare MLOps Pipeline</h2>
        <p className="mb-4 text-sm text-slate-500">Registry · drift-triggered retraining · champion vs challenger · manual approval · promotion.</p>
        <Flow />
        <div className="mt-4 grid grid-cols-3 gap-3">
          <Stat label="Production (champion)" value={prodV ? `v${prodV}` : "—"} tone={decision === "approved" ? "good" : undefined} hint={decision === "approved" ? "Just promoted from the challenger." : undefined} />
          <Stat label="Challenger" value={decision === "approved" ? "promoted ✓" : m.challenger_version ? `v${m.challenger_version}` : "—"} tone={decision === "approved" ? "good" : "warn"} />
          <Stat label="Serving artifact" value="present" tone="good" />
        </div>
      </Card>

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Model registry</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400 dark:border-slate-800">
              <th className="py-2 pr-4">Version</th><th className="pr-4">Alias</th><th className="pr-4">ROC-AUC</th><th className="pr-4">PR-AUC</th><th className="pr-4">Recall</th><th>Precision</th>
            </tr></thead>
            <tbody>
              {m.registry.map((r) => (
                <tr key={r.version} className="border-b border-slate-100 dark:border-slate-900">
                  <td className="py-2 pr-4 font-semibold">v{r.version}</td>
                  <td className="pr-4 text-slate-500">{aliasFor(r.version)}</td>
                  <td className="pr-4 tabular-nums">{r.roc_auc.toFixed(4)}</td>
                  <td className="pr-4 tabular-nums">{r.pr_auc.toFixed(4)}</td>
                  <td className="pr-4 tabular-nums">{r.recall.toFixed(4)}</td>
                  <td className="tabular-nums">{r.precision.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {dt.drifted != null && (
        <Card>
          <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Drift trigger — latest window vs training reference</h3>
          <p className="mb-3 text-xs text-slate-400">The run that triggered this retraining. {(dt.share_of_drifted_columns ?? 0) >= (dt.threshold ?? 1) ? "Drift exceeded the threshold → retrain." : "Below threshold."}</p>
          <div className="mb-3 grid grid-cols-3 gap-3">
            <Stat label="Drifted?" value={dt.drifted ? "YES" : "no"} tone={dt.drifted ? "crit" : "good"} />
            <Stat label="Share drifted" value={(dt.share_of_drifted_columns ?? 0).toFixed(2)} />
            <Stat label="Threshold" value={dt.threshold ?? "—"} />
          </div>
          <div className="space-y-2">
            {(dt.columns ?? []).map((c) => (
              <div key={c.feature} className="flex items-center gap-3 text-sm">
                <span className="w-32 shrink-0 text-slate-500">{c.feature}</span>
                <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800">
                  <div className="h-full rounded" style={{ width: `${Math.min(100, (c.PSI / 0.25) * 100)}%`, background: c.PSI < 0.1 ? C.good : c.PSI < 0.25 ? C.warn : C.crit }} />
                </div>
                <span className="w-16 shrink-0 text-right tabular-nums text-slate-400">{c.PSI.toFixed(3)}</span>
                <StatusPill status={c.status} />
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Champion vs Challenger (holdout)</h3>
        <GroupedBars groups={keys.map((k) => k.replace("_", "-").toUpperCase())}
          series={[
            { name: `Challenger v${m.challenger_version}`, color: C.brand, values: keys.map((k) => m.challenger_metrics[k] ?? 0) },
            { name: `Champion v${m.champion_version} (eval baseline)`, color: C.aqua, values: keys.map((k) => m.champion_metrics[k] ?? 0) },
          ]} />
        <div className="mt-3">
          <h4 className="mb-1 text-xs font-semibold text-slate-500">Promotion gate</h4>
          <ul className="mb-2 space-y-1 text-sm text-slate-600 dark:text-slate-300">
            {m.gate_reasons.map((r, i) => <li key={i}>• {r}</li>)}
          </ul>
          <div className={`rounded-lg px-3 py-2 text-sm font-semibold ${m.gate_passed ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"}`}>
            {m.gate_passed ? "GATE PASSED → eligible for approval" : "GATE FAILED → not promotable"}
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Manual approval gate (human-in-the-loop)</h3>
        {m.gate_passed && decision == null && (
          <>
            <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
              Challenger <strong>v{m.challenger_version}</strong> passed the gate and is awaiting sign-off (evaluated against champion v{m.champion_version}; v{m.prod_version} currently serving).
            </div>
            <div className="flex gap-3">
              <button onClick={approve} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-light">Approve &amp; promote</button>
              <button onClick={reject} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300">Reject</button>
            </div>
          </>
        )}
        {decision === "approved" && <div className="rounded-lg bg-emerald-100 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">v{m.challenger_version} promoted to PRODUCTION — it would now serve the Model Dashboard. (Recorded to the audit trail below.)</div>}
        {decision === "rejected" && <div className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">Challenger v{m.challenger_version} rejected — champion v{m.prod_version} stays in production.</div>}
        {!m.gate_passed && <p className="text-sm text-slate-500">Nothing promotable — the challenger did not pass the automated gate.</p>}

        <h4 className="mb-2 mt-5 text-xs font-semibold text-slate-500">Audit trail (real promotions)</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400 dark:border-slate-800">
              <th className="py-2 pr-4">When</th><th className="pr-4">Version</th><th className="pr-4">Approver</th><th className="pr-4">Action</th><th>Reason</th>
            </tr></thead>
            <tbody>
              {[...log].reverse().map((a, i) => (
                <tr key={i} className="border-b border-slate-100 dark:border-slate-900">
                  <td className="py-2 pr-4 whitespace-nowrap text-slate-500">{a.timestamp.replace("T", " ").slice(0, 16)}</td>
                  <td className="pr-4 font-semibold">v{a.challenger_version}</td>
                  <td className="pr-4 text-slate-500">{a.approver}</td>
                  <td className="pr-4"><span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">promoted</span></td>
                  <td className="text-slate-500">{a.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
