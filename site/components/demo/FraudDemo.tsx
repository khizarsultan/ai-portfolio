"use client";
import { useEffect, useState } from "react";
import { postJSON, getJSON, Card, Label, TextInput, Select, RunButton, ErrorNote, DevHint, Verdict, ProbabilityBar, Bars } from "./ui";
import { prettyFeature } from "./features";

type Example = { label: string; y: number; raw: Record<string, number> };
type Meta = { threshold: number; model_name: string; examples: Example[]; global_importance: { feature: string; importance: number }[] };
type Result = {
  probability: number; threshold: number; flag: boolean; label: string;
  amount: number; hour: number; global_importance: { feature: string; importance: number }[];
};

export default function FraudDemo() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [idx, setIdx] = useState(0);
  const [amount, setAmount] = useState<number>(0);
  const [res, setRes] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    getJSON<Meta>("/api/fraud").then((m) => { setMeta(m); if (m.examples[0]) setAmount(m.examples[0].raw.Amount); })
      .catch((e) => setErr((e as Error).message));
  }, []);

  function pick(i: number) { setIdx(i); if (meta) setAmount(meta.examples[i].raw.Amount); setRes(null); }

  async function run() {
    if (!meta) return;
    setLoading(true); setErr(""); setRes(null);
    const raw = { ...meta.examples[idx].raw, Amount: amount };
    try { setRes(await postJSON<Result>("/api/fraud", { raw })); }
    catch (e) { setErr((e as Error).message); }
    finally { setLoading(false); }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <h2 className="mb-4 text-lg font-semibold">Transaction</h2>
        {!meta && !err && <p className="text-sm text-slate-400">Loading preset transactions…</p>}
        {meta && (
          <div className="space-y-4">
            <div><Label>Preset (real benchmark transaction)</Label>
              <Select value={idx} onChange={(e) => pick(+e.target.value)}>
                {meta.examples.map((ex, i) => <option key={i} value={i}>{ex.label}</option>)}
              </Select>
            </div>
            <div><Label>Amount ($) — editable, re-scored live</Label>
              <TextInput type="number" step={0.01} value={amount} onChange={(e) => setAmount(+e.target.value)} />
            </div>
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:bg-slate-800/50">
              The 28 features <code>V1…V28</code> are anonymized PCA components (privacy-preserving) carried from
              the selected real transaction. You edit the amount; the model re-scores.
            </p>
            <RunButton loading={loading} onClick={run}>Score transaction</RunButton>
          </div>
        )}
        {err && <div className="mt-4"><ErrorNote msg={err} /><DevHint /></div>}
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold">Result</h2>
        {!res && !loading && <p className="text-sm text-slate-400">Pick a transaction and score it.</p>}
        {res && (
          <div className="space-y-5">
            <Verdict flag={res.flag} label={res.label} />
            <ProbabilityBar value={res.probability} threshold={res.threshold} danger={res.flag} />
            <p className="text-xs text-slate-400">Amount ${res.amount.toFixed(2)} · hour of day {res.hour}</p>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">What the model weighs most</h3>
              <Bars items={res.global_importance.slice(0, 10).map((g) => ({ label: prettyFeature(g.feature), value: g.importance }))} />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
