"use client";
// Executive Summary (URL threats) — plain-language business view. Ports the
// Streamlit executive_view: assumptions drive the money live; catch-rate /
// precision are model properties (multiclass argmax, no threshold knob).
import { useState } from "react";
import { Card, Label, TextInput, Select } from "../ui";
import { Stat, StackedBar, Ring, C } from "../charts";
import type { UrlData } from "./types";

export default function Executive({ d }: { d: UrlData }) {
  const [valueThreat, setValueThreat] = useState(50);
  const [costBlock, setCostBlock] = useState(3);
  const [volume, setVolume] = useState(1_000_000);
  const [basis, setBasis] = useState<"Monthly" | "Annual">("Monthly");

  const classes = d.classes;
  const bi = classes.indexOf("benign");
  const cc = d.confusion_counts;
  const total = cc.flat().reduce((a, b) => a + b, 0);
  const mal = classes.map((_, i) => i).filter((i) => i !== bi);
  const trueMal = mal.reduce((s, r) => s + cc[r].reduce((a, b) => a + b, 0), 0);
  const caught = mal.reduce((s, r) => s + mal.reduce((a, c) => a + cc[r][c], 0), 0);
  const missed = mal.reduce((s, r) => s + cc[r][bi], 0);
  const falseBlock = mal.reduce((s, c) => s + cc[bi][c], 0);
  const cleared = cc[bi][bi];
  const catchRate = trueMal ? caught / trueMal : 0;
  const alertPrec = caught + falseBlock ? caught / (caught + falseBlock) : 0;
  const f1 = d.metrics.macro_f1;

  const mult = basis === "Annual" ? 12 : 1;
  const per = basis === "Annual" ? "year" : "month";
  const nCaught = (caught / total) * volume * mult;
  const nMissed = (missed / total) * volume * mult;
  const nFb = (falseBlock / total) * volume * mult;
  const gross = nCaught * valueThreat;
  const blockCost = nFb * costBlock;
  const net = gross - blockCost;
  const perUrl = volume ? net / (volume * mult) : 0;
  const upt = nCaught ? (volume * mult) / nCaught : 0;
  const missedExposure = nMissed * valueThreat;
  const money = (x: number) => `$${Math.round(x).toLocaleString()}`;

  const grade = f1 >= 0.9 ? "Strong" : f1 >= 0.8 ? "Good" : f1 >= 0.7 ? "Fair" : "Needs work";
  const goodGrade = grade === "Strong" || grade === "Good";
  const worst = d.drift.reduce((a, b) => (["DRIFT", "WARNING", "OK"].indexOf(b.status) < ["DRIFT", "WARNING", "OK"].indexOf(a.status) ? b : a), d.drift[0]);
  const sc = 10000 / total;
  const maxBar = Math.max(gross, blockCost, Math.abs(net), 1);

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg font-semibold">Malicious URL Detection — Business Summary</h2>
        <p className="mt-1 text-sm text-slate-500">Plain-language view — adjust the assumptions and the dollars update live. <em>Illustrative.</em></p>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div><Label>Time basis</Label>
            <Select value={basis} onChange={(e) => setBasis(e.target.value as "Monthly" | "Annual")}><option>Monthly</option><option>Annual</option></Select></div>
          <div><Label>Value of blocking one threat ($)</Label>
            <TextInput type="number" value={valueThreat} onChange={(e) => setValueThreat(Math.max(0, +e.target.value))} /></div>
          <div><Label>Cost of one false block ($)</Label>
            <TextInput type="number" value={costBlock} onChange={(e) => setCostBlock(Math.max(0, +e.target.value))} /></div>
          <div><Label>URLs scanned / month</Label>
            <TextInput type="number" value={volume} onChange={(e) => setVolume(Math.max(0, +e.target.value))} /></div>
        </div>
      </Card>

      <div className={`rounded-2xl border px-5 py-4 text-sm ${goodGrade ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200" : "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"}`}>
        Overall reliability: <strong>{grade}</strong>. Across all four URL types the model scores a balanced accuracy (macro-F1) of <strong>{f1.toFixed(2)}</strong> out of 1.00.
      </div>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">At a glance</h3>
        <div className="grid grid-cols-2 items-center gap-4 md:grid-cols-4">
          <Ring value={catchRate} label="Blocks real threats (catch rate)" color={C.brand} />
          <Ring value={alertPrec} label="Blocks that are correct" color={C.aqua} />
          <Ring value={f1} label="Balanced accuracy (macro-F1)" color={C.good} />
          <div className="grid gap-3">
            <Stat label="Speed per URL" value="Instant" hint={`~${d.latency.p95.toFixed(0)} ms (p95).`} />
            <Stat label="Model in use" value={d.prod_version ? `v${d.prod_version}` : "live"} />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">What happens for every 10,000 URLs scanned</h3>
        <p className="mb-3 text-xs text-slate-400">Held-out results, all malicious types combined into &ldquo;threats&rdquo;.</p>
        <StackedBar segments={[
          { label: "Threats blocked", value: caught * sc, color: C.good },
          { label: "Threats missed", value: missed * sc, color: C.crit },
          { label: "Safe URLs false-blocked", value: falseBlock * sc, color: C.warn },
          { label: "Safe URLs allowed", value: cleared * sc, color: C.brand },
        ]} />
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Estimated business impact ({per}ly)</h3>
        <p className="mb-3 text-xs text-slate-400">Threat value blocked {money(gross)} − false-block cost {money(blockCost)} = <strong>{money(net)} per {per}</strong>. Illustrative.</p>
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            {[{ l: "Threat value blocked", v: gross, c: C.good },
              { l: "False-block cost", v: blockCost, c: C.warn },
              { l: "Net value", v: net, c: net >= 0 ? C.brand : C.crit }].map((b) => (
              <div key={b.l} className="text-sm">
                <div className="mb-0.5 flex justify-between"><span className="text-slate-500">{b.l}</span><span className="font-semibold tabular-nums">{money(b.v)}</span></div>
                <div className="h-3 w-full rounded bg-slate-100 dark:bg-slate-800"><div className="h-full rounded" style={{ width: `${(Math.abs(b.v) / maxBar) * 100}%`, background: b.c }} /></div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Stat label={`Net value / ${per}`} value={money(net)} tone={net >= 0 ? "good" : "crit"} />
            <Stat label={`Threats blocked / ${per}`} value={nCaught.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="Value / URL" value={`$${perUrl.toFixed(4)}`} />
            <Stat label="URLs per threat caught" value={upt.toLocaleString(undefined, { maximumFractionDigits: 0 })} />
            <Stat label="Threat catch rate" value={`${Math.round(catchRate * 100)}%`} />
            <Stat label={`Missed-threat exposure / ${per}`} value={money(missedExposure)} tone="crit" />
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-1 text-sm font-semibold text-slate-600 dark:text-slate-300">Can we still trust it?</h3>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {worst.status === "DRIFT" ? "Incoming URL traffic has shifted from training — a model refresh is recommended."
            : worst.status === "WARNING" ? "URL traffic is drifting slightly — worth monitoring."
            : "Incoming URL traffic looks like the training data, so results remain trustworthy."} (data drift)
        </p>
        <p className="mt-2 text-xs text-slate-400">Updates are proposed automatically on drift, checked vs the current model, and go live only after a human approves — see the MLOps Pipeline tab.</p>
      </Card>
    </div>
  );
}
