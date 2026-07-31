"use client";
// Executive Summary — configurable, plain-language business view for stakeholders.
// Ports the Streamlit executive_view: every assumption AND the alert sensitivity
// drive the KPIs and visuals live, all client-side. Sensitivity moves the model's
// decision threshold via the precomputed sweep, so detection/precision, the
// per-1,000 outcomes, and the money all react together.
import { useState } from "react";
import { Card, Label, TextInput, Select } from "../ui";
import { Stat, StackedBar, Ring, C } from "../charts";
import type { DemoData } from "./types";
import { nearestSweep } from "./types";

export default function Executive({ d }: { d: DemoData }) {
  const [valueCase, setValueCase] = useState(1200);
  const [costAlarm, setCostAlarm] = useState(80);
  const [volume, setVolume] = useState(10000);
  const [basis, setBasis] = useState<"Monthly" | "Annual">("Monthly");
  const [thr, setThr] = useState(d.threshold_default);

  const row = nearestSweep(d.sweep, thr);
  const { tp, fp, fn, tn } = row;
  const total = tp + fp + fn + tn;
  const recall = row.recall, precision = row.precision, roc = d.scores.ROC_AUC;

  const mult = basis === "Annual" ? 12 : 1;
  const per = basis === "Annual" ? "year" : "month";
  const caught = (tp / total) * volume * mult;
  const alarms = (fp / total) * volume * mult;
  const missed = (fn / total) * volume * mult;
  const gross = caught * valueCase;
  const alarmCost = alarms * costAlarm;
  const net = gross - alarmCost;
  const perPatient = volume ? net / (volume * mult) : 0;
  const nns = caught ? (volume * mult) / caught : 0;
  const missedExposure = missed * valueCase;
  const money = (x: number) => `$${Math.round(x).toLocaleString()}`;

  const grade = roc >= 0.9 ? "Strong" : roc >= 0.8 ? "Good" : roc >= 0.7 ? "Fair" : "Needs work";
  const goodGrade = grade === "Strong" || grade === "Good";
  const worstDrift = d.drift.reduce((a, b) => (["DRIFT", "WARNING", "OK"].indexOf(b.status) < ["DRIFT", "WARNING", "OK"].indexOf(a.status) ? b : a), d.drift[0]);

  const scale = 1000 / total;
  const p1000 = { caught: tp * scale, missed: fn * scale, alarms: fp * scale, cleared: tn * scale };
  const maxBar = Math.max(gross, alarmCost, Math.abs(net), 1);

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg font-semibold">Diabetes Risk Model — Business Summary</h2>
        <p className="mt-1 text-sm text-slate-500">Plain-language view — adjust the assumptions and every number and chart updates live. <em>Illustrative.</em></p>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div><Label>Time basis</Label>
            <Select value={basis} onChange={(e) => setBasis(e.target.value as "Monthly" | "Annual")}>
              <option>Monthly</option><option>Annual</option>
            </Select></div>
          <div><Label>Value of catching one case ($)</Label>
            <TextInput type="number" value={valueCase} onChange={(e) => setValueCase(Math.max(0, +e.target.value))} /></div>
          <div><Label>Cost of one false alarm ($)</Label>
            <TextInput type="number" value={costAlarm} onChange={(e) => setCostAlarm(Math.max(0, +e.target.value))} /></div>
          <div><Label>Patients screened / month</Label>
            <TextInput type="number" value={volume} onChange={(e) => setVolume(Math.max(0, +e.target.value))} /></div>
        </div>
        <div className="mt-4">
          <Label>Alert sensitivity — {recall >= 0.8 ? "catch more (sensitive)" : recall <= 0.5 ? "fewer alerts (specific)" : "balanced"}</Label>
          <input type="range" min={0.05} max={0.95} step={0.02} value={thr}
            onChange={(e) => setThr(+e.target.value)} className="w-full accent-brand" />
          <p className="text-xs text-slate-400">Slide <strong>left</strong> to catch more at-risk patients (higher detection, more false alarms); <strong>right</strong> for fewer, more-certain alerts. This moves the model&apos;s decision threshold and updates every number and chart below.</p>
        </div>
      </Card>

      <div className={`rounded-2xl border px-5 py-4 text-sm ${goodGrade ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200" : "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"}`}>
        Overall reliability: <strong>{grade}</strong>. The model correctly tells high-risk from low-risk patients about <strong>{Math.round(roc * 100)} times out of 100</strong>.
        {d.mlops.gate_passed && <> A newer model has passed automated checks and is <strong>awaiting approval</strong> on the MLOps Pipeline tab.</>}
      </div>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">At a glance</h3>
        <div className="grid grid-cols-2 items-center gap-4 md:grid-cols-4">
          <Ring value={recall} label="Catches true cases (detection)" color={C.brand} />
          <Ring value={precision} label="Alerts that are correct" color={C.aqua} />
          <Ring value={roc} label="Overall reliability (ROC-AUC)" color={C.good} />
          <div className="grid gap-3">
            <Stat label="Speed per patient" value="Instant" hint={`~${d.latency.p95.toFixed(0)} ms (p95).`} />
            <Stat label="Model in use" value={d.prod_version ? `v${d.prod_version}` : "live"} />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">What happens for every 1,000 patients screened</h3>
        <p className="mb-3 text-xs text-slate-400">At the current alert sensitivity, on held-out patients.</p>
        <StackedBar segments={[
          { label: "At-risk caught", value: p1000.caught, color: C.good },
          { label: "At-risk missed", value: p1000.missed, color: C.crit },
          { label: "False alarms", value: p1000.alarms, color: C.warn },
          { label: "Correctly cleared", value: p1000.cleared, color: C.brand },
        ]} />
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Estimated business impact ({per}ly)</h3>
        <p className="mb-3 text-xs text-slate-400">Early-detection value {money(gross)} − false-alarm cost {money(alarmCost)} = <strong>{money(net)} per {per}</strong>. Illustrative.</p>
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            {[{ l: "Value created (early detection)", v: gross, c: C.good },
              { l: "False-alarm cost", v: alarmCost, c: C.warn },
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
            <Stat label={`Cases caught / ${per}`} value={caught.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="Value / patient" value={`$${perPatient.toFixed(2)}`} />
            <Stat label="Patients per case caught" value={nns.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="Detection rate" value={`${Math.round(recall * 100)}%`} />
            <Stat label={`Missed-case exposure / ${per}`} value={money(missedExposure)} tone="crit" />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Can we still trust it?</h3>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {worstDrift.status === "DRIFT" ? "The incoming patient population has shifted from what the model learned — a refresh is recommended."
            : worstDrift.status === "WARNING" ? "The patient population is drifting slightly — worth monitoring."
            : "The incoming patient population looks like the data the model learned from, so its results remain trustworthy."}
          {" "}(data drift)
        </p>
        <p className="mt-2 text-xs text-slate-400">Model updates are proposed automatically when data shifts, checked against the current model, and go live only after a human approves — see the MLOps Pipeline tab.</p>
      </Card>
    </div>
  );
}
