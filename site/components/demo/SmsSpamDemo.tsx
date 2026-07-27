"use client";
import { useEffect, useState } from "react";
import { postJSON, getJSON, Card, Label, TextArea, RunButton, ErrorNote, DevHint, Verdict, ProbabilityBar, SignedBars } from "./ui";

type Meta = { threshold: number; model_name: string; examples: { label: string; text: string }[] };
type Result = {
  probability: number; threshold: number; flag: boolean; label: string;
  tokens: { token: string; contribution: number }[];
};

export default function SmsSpamDemo() {
  const [text, setText] = useState("Congratulations! You've WON a FREE $1000 gift card. Click http://bit.ly/claim now to claim.");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { getJSON<Meta>("/api/sms-spam").then(setMeta).catch(() => {}); }, []);

  async function run(t?: string) {
    const target = (t ?? text).trim();
    if (!target) return;
    setText(target); setLoading(true); setErr(""); setRes(null);
    try { setRes(await postJSON<Result>("/api/sms-spam", { text: target })); }
    catch (e) { setErr((e as Error).message); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <Card>
        <Label>SMS message</Label>
        <TextArea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste a text message…" />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <RunButton loading={loading} onClick={() => run()}>Classify</RunButton>
          {meta?.examples.map((ex) => (
            <button key={ex.label} onClick={() => run(ex.text)}
              className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-brand hover:text-white dark:bg-slate-800 dark:text-slate-300">
              {ex.label}
            </button>
          ))}
        </div>
        {err && <div className="mt-4"><ErrorNote msg={err} /><DevHint /></div>}
      </Card>

      {res && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <h2 className="mb-4 text-lg font-semibold">Result</h2>
            <Verdict flag={res.flag} label={res.label} />
            <div className="mt-5"><ProbabilityBar value={res.probability} threshold={res.threshold} danger={res.flag} /></div>
          </Card>
          <Card>
            <h2 className="mb-1 text-lg font-semibold">Why — words that drove it</h2>
            <p className="mb-4 text-xs text-slate-400">Red = pushes toward spam · blue = toward benign. Exact contribution = tf-idf × model weight.</p>
            {res.tokens.length ? (
              <SignedBars items={res.tokens.map((t) => ({ label: t.token, value: t.contribution }))} />
            ) : (
              <p className="text-sm text-slate-400">No in-vocabulary words to attribute.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
