"use client";
import { useEffect, useState } from "react";
import { postJSON, getJSON, Card, Label, TextInput, RunButton, ErrorNote, DevHint, Verdict } from "./ui";
import StageFlow, { Stage } from "./StageFlow";

type Meta = { classes: string[]; examples: Record<string, string[]>; model_name: string };
type Result = {
  url: string; predicted_class: string; malicious: boolean;
  probabilities: Record<string, number>;
  flags: { key: string; label: string; on: boolean }[];
  features: { url_len: number; host_len: number; n_subdomains: number; url_entropy: number };
  stages?: Stage[];
};

const CLASS_COLOR: Record<string, string> = {
  benign: "text-emerald-600", phishing: "text-red-600", malware: "text-red-600", defacement: "text-amber-600",
};

export default function MaliciousUrlDemo() {
  const [url, setUrl] = useState("http://paypal.com.secure-login.account-verify.com/signin");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { getJSON<Meta>("/api/malicious-url").then(setMeta).catch(() => {}); }, []);

  async function run(u?: string) {
    const target = (u ?? url).trim();
    if (!target) return;
    setUrl(target); setLoading(true); setErr(""); setRes(null);
    try { setRes(await postJSON<Result>("/api/malicious-url", { url: target })); }
    catch (e) { setErr((e as Error).message); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <Card>
        <Label>URL</Label>
        <div className="flex gap-2">
          <TextInput value={url} onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()} placeholder="Paste a URL…" />
          <RunButton loading={loading} onClick={() => run()}>Classify</RunButton>
        </div>
        {meta && (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-slate-400">Try:</span>
            {Object.entries(meta.examples).map(([cls, urls]) => (
              <button key={cls} onClick={() => run(urls[0])}
                className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 hover:bg-brand hover:text-white dark:bg-slate-800 dark:text-slate-300">
                {cls}
              </button>
            ))}
          </div>
        )}
        {err && <div className="mt-4"><ErrorNote msg={err} /><DevHint /></div>}
      </Card>

      {res && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <h2 className="mb-4 text-lg font-semibold">Classification</h2>
            <Verdict flag={res.malicious} label={res.malicious ? `Malicious — ${res.predicted_class}` : "Benign"} />
            <div className="mt-5 space-y-2">
              {Object.entries(res.probabilities).sort((a, b) => b[1] - a[1]).map(([cls, p]) => (
                <div key={cls} className="flex items-center gap-2 text-sm">
                  <span className={`w-24 shrink-0 font-medium ${CLASS_COLOR[cls] ?? "text-slate-500"}`}>{cls}</span>
                  <div className="relative h-3 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div className="h-full rounded-full bg-brand" style={{ width: `${p * 100}%` }} />
                  </div>
                  <span className="w-12 shrink-0 tabular-nums text-slate-400">{(p * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <h2 className="mb-4 text-lg font-semibold">Why — lexical signals</h2>
            <div className="mb-4 flex flex-wrap gap-2">
              {res.flags.map((fl) => (
                <span key={fl.key}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    fl.on ? (fl.key === "has_https" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                                     : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300")
                          : "bg-slate-100 text-slate-400 dark:bg-slate-800"}`}>
                  {fl.on ? "● " : "○ "}{fl.label}
                </span>
              ))}
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-slate-400">URL length</dt><dd className="font-semibold tabular-nums">{res.features.url_len}</dd></div>
              <div><dt className="text-slate-400">Host length</dt><dd className="font-semibold tabular-nums">{res.features.host_len}</dd></div>
              <div><dt className="text-slate-400">Subdomains</dt><dd className="font-semibold tabular-nums">{res.features.n_subdomains}</dd></div>
              <div><dt className="text-slate-400">URL entropy</dt><dd className="font-semibold tabular-nums">{res.features.url_entropy}</dd></div>
            </dl>
          </Card>
        </div>
      )}

      {res?.stages && (
        <Card>
          <h2 className="mb-1 text-lg font-semibold">Under the hood</h2>
          <p className="mb-4 text-sm text-slate-500">
            The real pipeline, step by step — click any stage to see the actual values.
          </p>
          <StageFlow stages={res.stages} />
        </Card>
      )}
    </div>
  );
}
