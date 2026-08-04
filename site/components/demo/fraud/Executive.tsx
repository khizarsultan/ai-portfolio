"use client";
// Executive Summary (fraud) — plain-language business view. Alert sensitivity moves
// the decision threshold via the precomputed sweep, so detection, false-alarm rate,
// the per-10,000 outcomes and the money all react together. Highly imbalanced, so the
// story is recall vs review cost, not raw accuracy.
import { useState } from "react";
import { Card, Label, TextInput, Select } from "../ui";
import { Stat, StackedBar, Ring, C } from "../charts";
import type { FraudData } from "./types";
import { nearestSweep } from "./types";

export default function Executive({ d }: { d: FraudData }) {
  const [valueFraud, setValueFraud] = useState(150);
  const [costReview, setCostReview] = useState(4);
  const [volume, setVolume] = useState(1_000_000);
  const [basis, setBasis] = useState<"Monthly" | "Annual">("Monthly");
  const [thr, setThr] = useState(d.threshold_default);

  const row = nearestSweep(d.sweep, thr);
  const { tp, fp, fn, tn } = row;
  const total = tp + fp + fn + tn;
  const recall = row.recall, precision = row.precision, prauc = d.scores.PR_AUC;

  const mult = basis === "Annual" ? 12 : 1;
  const per = basis === "Annual" ? "year" : "month";
  const caught = (tp / total) * volume * mult;
  const alarms = (fp / total) * volume * mult;
  const missed = (fn / total) * volume * mult;
  const gross = caught * valueFraud;
  const reviewCost = alarms * costReview;
  const net = gross - reviewCost;
  const perTxn = volume ? net / (volume * mult) : 0;
  const missedExposure = missed * valueFraud;
  const money = (x: number) => `$${Math.round(x).toLocaleString()}`;

  // Under extreme imbalance ROC saturates; grade on PR-AUC (the honest metric).
  const grade = prauc >= 0.8 ? "Strong" : prauc >= 0.65 ? "Good" : prauc >= 0.45 ? "Fair" : "Needs work";
  const goodGrade = grade === "Strong" || grade === "Good";
  const worstDrift = d.drift.reduce((a, b) => (["DRIFT", "WARNING", "OK"].indexOf(b.status) < ["DRIFT", "WARNING", "OK"].indexOf(a.status) ? b : a), d.drift[0]);

  const scale = 10000 / total;
  const p10k = { caught: tp * scale, missed: fn * scale, alarms: fp * scale, cleared: tn * scale };
  const maxBar = Math.max(gross, reviewCost, Math.abs(net), 1);

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg font-semibold">Credit-Card Fraud Detection — Business Summary</h2>
        <p className="mt-1 text-sm text-slate-500">Plain-language view — adjust the assumptions and every number and chart updates live. <em>Illustrative.</em></p>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div><Label>Time basis</Label>
            <Select value={basis} onChange={(e) => setBasis(e.target.value as "Monthly" | "Annual")}>
              <option>Monthly</option><option>Annual</option>
            </Select></div>
          <div><Label>Value of blocking one fraud ($)</Label>
            <TextInput type="number" value={valueFraud} onChange={(e) => setValueFraud(Math.max(0, +e.target.value))} /></div>
          <div><Label>Cost of one false alarm review ($)</Label>
            <TextInput type="number" value={costReview} onChange={(e) => setCostReview(Math.max(0, +e.target.value))} /></div>
          <div><Label>Transactions / month</Label>
            <TextInput type="number" value={volume} onChange={(e) => setVolume(Math.max(0, +e.target.value))} /></div>
        </div>
        <div className="mt-4">
          <Label>Alert sensitivity — {recall >= 0.8 ? "catch more (sensitive)" : recall <= 0.5 ? "fewer alerts (specific)" : "balanced"}</Label>
          <input type="range" min={0.05} max={0.95} step={0.02} value={thr}
            onChange={(e) => setThr(+e.target.value)} className="w-full accent-brand" />
          <p className="text-xs text-slate-400">Slide <strong>left</strong> to catch more fraud (higher detection, more false alarms to review); <strong>right</strong> for fewer, more-certain blocks. This moves the model&apos;s decision threshold and updates every number and chart below.</p>
        </div>
      </Card>

      <div className={`rounded-2xl border px-5 py-4 text-sm ${goodGrade ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200" : "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"}`}>
        Overall reliability: <strong>{grade}</strong>. Fraud is rare (~{(d.baseline * 100).toFixed(2)}% of transactions), so raw accuracy is misleading — the model&apos;s balanced fraud-catching score (PR-AUC) is <strong>{prauc.toFixed(2)}</strong> out of 1.00.
      </div>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">At a glance</h3>
        <div className="grid grid-cols-2 items-center gap-4 md:grid-cols-4">
          <Ring value={recall} label="Fraud caught (detection)" color={C.brand} />
          <Ring value={precision} label="Blocks that are real fraud" color={C.aqua} />
          <Ring value={prauc} label="Fraud-catching score (PR-AUC)" color={C.good} />
          <div className="grid gap-3">
            <Stat label="Speed per transaction" value="Instant" hint={`~${d.latency.p95.toFixed(0)} ms (p95).`} />
            <Stat label="Model in use" value={d.prod_version ? `v${d.prod_version}` : "live"} />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">What happens for every 10,000 transactions</h3>
        <p className="mb-3 text-xs text-slate-400">At the current alert sensitivity, on held-out transactions. Fraud is rare, so &ldquo;cleared&rdquo; dominates.</p>
        <StackedBar segments={[
          { label: "Fraud blocked", value: p10k.caught, color: C.good },
          { label: "Fraud missed", value: p10k.missed, color: C.crit },
          { label: "False alarms", value: p10k.alarms, color: C.warn },
          { label: "Correctly cleared", value: p10k.cleared, color: C.brand },
        ]} />
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Estimated business impact ({per}ly)</h3>
        <p className="mb-3 text-xs text-slate-400">Fraud value blocked {money(gross)} − false-alarm review cost {money(reviewCost)} = <strong>{money(net)} per {per}</strong>. Illustrative.</p>
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            {[{ l: "Fraud value blocked", v: gross, c: C.good },
              { l: "False-alarm review cost", v: reviewCost, c: C.warn },
              { l: "Net value", v: net, c: net >= 0 ? C.brand : C.crit }].map((b) => (
              <div key={b.l} className="text-sm">
                <div className="mb-0.5 flex justify-between"><span className="text-slate-500">{b.l}</span><span className="font-semibold tabular-nums">{money(b.v)}</span></div>
                <div className="h-3 w-full rounded bg-slate-100 dark:bg-slate-800">
                  <div className="h-full rounded" style={{ width: `${(Math.abs(b.v) / maxBar) * 100}%`, background: b.c }} />
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Stat label={`Net value / ${per}`} value={money(net)} tone={net >= 0 ? "good" : "crit"} />
            <Stat label={`Fraud blocked / ${per}`} value={caught.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="Value / transaction" value={`$${perTxn.toFixed(4)}`} />
            <Stat label={`False alarms / ${per}`} value={alarms.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="Fraud catch rate" value={`${Math.round(recall * 100)}%`} />
            <Stat label={`Missed-fraud exposure / ${per}`} value={money(missedExposure)} tone="crit" />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Can we still trust it?</h3>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {worstDrift.status === "DRIFT" ? "Incoming transaction patterns have shifted from what the model learned — a refresh is recommended."
            : worstDrift.status === "WARNING" ? "Transaction patterns are drifting slightly — worth monitoring."
            : "Incoming transaction patterns look like the data the model learned from, so its results remain trustworthy."}
          {" "}(data drift)
        </p>
        <p className="mt-2 text-xs text-slate-400">Model updates are proposed automatically when data shifts, checked against the current model, and go live only after a human approves — see the MLOps Pipeline tab.</p>
      </Card>
    </div>
  );
}
