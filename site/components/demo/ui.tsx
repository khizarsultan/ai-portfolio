"use client";
import { ReactNode } from "react";

// ---- data helper ---------------------------------------------------------
export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as { error?: string }).error || `Request failed (${r.status})`);
  return data as T;
}

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(path);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as { error?: string }).error || `Request failed (${r.status})`);
  return data as T;
}

// ---- layout --------------------------------------------------------------
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}>
      {children}
    </div>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="mb-1 block text-sm font-medium text-slate-600 dark:text-slate-300">{children}</label>;
}

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand focus:ring-1 focus:ring-brand dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100";

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={inputCls} />;
}
export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${inputCls} resize-y`} />;
}
export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={inputCls} />;
}

export function RunButton({ loading, className = "", children, ...rest }: { loading?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      disabled={loading || rest.disabled}
      className={`inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-light disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
    >
      {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
      {children}
    </button>
  );
}

export function ErrorNote({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
      {msg}
    </div>
  );
}

// Local-dev note: `next dev` does not run the Python functions (only `vercel dev`
// or a real deployment does). Shown when a request fails to reach the API.
export function DevHint() {
  return (
    <p className="mt-2 text-xs text-slate-400">
      Note: the prediction runs on a Python serverless function. It works on the deployed site (and with{" "}
      <code>vercel dev</code>), but not under a plain <code>next dev</code> server.
    </p>
  );
}

// ---- evaluation scores ---------------------------------------------------
export type EvalMetric = { key: string; label: string; score: number; tone: "good" | "warn" | "bad"; detail: string };

const EVAL_BAR: Record<string, string> = { good: "bg-emerald-500", warn: "bg-amber-500", bad: "bg-red-500" };
const EVAL_TEXT: Record<string, string> = {
  good: "text-emerald-600 dark:text-emerald-400",
  warn: "text-amber-600 dark:text-amber-400",
  bad: "text-red-600 dark:text-red-400",
};

export function EvalScores({ metrics }: { metrics: EvalMetric[] }) {
  if (!metrics?.length) return null;
  const avg = Math.round(metrics.reduce((a, m) => a + m.score, 0) / metrics.length);
  const overallTone = avg >= 80 ? "good" : avg >= 50 ? "warn" : "bad";
  return (
    <Card className="!p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-500">Evaluation scores</h2>
        <div className={`text-xl font-bold tabular-nums ${EVAL_TEXT[overallTone]}`}>{avg}<span className="text-xs font-medium text-slate-400">/100</span></div>
      </div>
      <p className="mt-0.5 text-[11px] text-slate-400">How correct, grounded &amp; reliable this run is.</p>
      <div className="mt-4 space-y-3">
        {metrics.map((m) => (
          <div key={m.key} title={m.detail}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[13px] font-medium leading-tight text-slate-700 dark:text-slate-200">{m.label}</span>
              <span className={`text-[13px] font-bold tabular-nums ${EVAL_TEXT[m.tone]}`}>{m.score}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div className={`h-full rounded-full ${EVAL_BAR[m.tone]} transition-all duration-700`} style={{ width: `${m.score}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---- result widgets ------------------------------------------------------
export function Verdict({ flag, label, dangerIsTrue = true }: { flag: boolean; label: string; dangerIsTrue?: boolean }) {
  const danger = flag === dangerIsTrue;
  return (
    <div
      className={`rounded-xl px-4 py-3 text-center text-lg font-bold ${
        danger
          ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
          : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
      }`}
    >
      {label}
    </div>
  );
}

export function ProbabilityBar({ value, threshold, danger }: { value: number; threshold?: number; danger?: boolean }) {
  const pct = Math.round(value * 1000) / 10;
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-slate-500">Probability</span>
        <span className="font-semibold tabular-nums">{pct}%</span>
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div
          className={`h-full rounded-full ${danger ? "bg-red-500" : "bg-emerald-500"}`}
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
        {threshold != null && (
          <div
            className="absolute top-0 h-full w-0.5 bg-slate-900 dark:bg-white"
            style={{ left: `${Math.min(100, Math.max(0, threshold * 100))}%` }}
            title={`Decision threshold ${Math.round(threshold * 100)}%`}
          />
        )}
      </div>
      {threshold != null && (
        <p className="mt-1 text-xs text-slate-400">Vertical line = decision threshold ({Math.round(threshold * 100)}%).</p>
      )}
    </div>
  );
}

// Signed horizontal bars (red = positive/toward-flag, blue = negative).
export function SignedBars({ items, max }: { items: { label: string; value: number }[]; max?: number }) {
  const m = max ?? Math.max(1e-9, ...items.map((i) => Math.abs(i.value)));
  return (
    <div className="space-y-1.5">
      {items.map((it) => {
        const w = (Math.abs(it.value) / m) * 100;
        const pos = it.value >= 0;
        return (
          <div key={it.label} className="flex items-center gap-2 text-sm">
            <span className="w-28 shrink-0 truncate text-right text-slate-500" title={it.label}>{it.label}</span>
            <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800">
              <div
                className={`h-full rounded ${pos ? "bg-red-400" : "bg-blue-400"}`}
                style={{ width: `${w}%` }}
              />
            </div>
            <span className="w-14 shrink-0 tabular-nums text-slate-400">{it.value.toFixed(3)}</span>
          </div>
        );
      })}
    </div>
  );
}

// Plain (unsigned) importance bars.
export function Bars({ items }: { items: { label: string; value: number }[] }) {
  const m = Math.max(1e-9, ...items.map((i) => i.value));
  return (
    <div className="space-y-1.5">
      {items.map((it) => (
        <div key={it.label} className="flex items-center gap-2 text-sm">
          <span className="w-40 shrink-0 truncate text-right text-slate-500" title={it.label}>{it.label}</span>
          <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800">
            <div className="h-full rounded bg-brand" style={{ width: `${(it.value / m) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
