"use client";
import { useEffect, useState } from "react";

// A stage in a model's pipeline, carrying the REAL intermediate values at that point.
export type Stage = {
  key: string;
  title: string;
  summary: string;
  kind: "kv" | "flags" | "vector" | "bars" | "importance";
  data: unknown;
};

const FLAG_TONE: Record<string, "good" | "warn"> = {
  has_https: "good", has_at: "warn", has_ip: "warn", is_shortened: "warn", has_suspicious: "warn",
};

// Each pipeline stage owns a hue; the sequence reads indigo→teal, a journey from raw data to
// explanation. Keyed by stage so every ML demo that reuses these keys stays consistent; unknown
// keys fall back to the ordered spectrum.
const STAGE_COLORS: Record<string, string> = {
  input: "#64748b", features: "#6366f1", flags: "#f59e0b", preprocess: "#8b5cf6",
  model: "#2563eb", prediction: "#0ea5e9", explain: "#14b8a6", tokens: "#f59e0b",
};
const SPECTRUM = ["#6366f1", "#8b5cf6", "#7c3aed", "#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b"];
const colorFor = (key: string, i: number) => STAGE_COLORS[key] ?? SPECTRUM[i % SPECTRUM.length];

function lighten(hex: string, amt: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const m = (c: number) => Math.round(c + (255 - c) * amt);
  return `rgb(${m(r)},${m(g)},${m(b)})`;
}

export default function StageFlow({ stages }: { stages: Stage[] }) {
  const [revealed, setRevealed] = useState(0);
  const [active, setActive] = useState(0);

  // Reveal stages left-to-right, then open the final (prediction/explanation) stage.
  useEffect(() => {
    setRevealed(0);
    setActive(0);
    const t = setInterval(() => {
      setRevealed((r) => {
        if (r >= stages.length) { clearInterval(t); return r; }
        setActive(r);
        return r + 1;
      });
    }, 380);
    return () => clearInterval(t);
  }, [stages]);

  if (!stages?.length) return null;
  const cur = stages[active];

  // ---- SVG pipeline-graph layout (left→right DAG) ----
  const NW = 146, NH = 42, GAP = 38, PADX = 6, TOP = 10;
  const step = NW + GAP;
  const vw = PADX * 2 + stages.length * NW + (stages.length - 1) * GAP;
  const vh = TOP + NH + 8;
  const nx = (i: number) => PADX + i * step;
  const ny = TOP;
  const cyN = ny + NH / 2;

  return (
    <div>
      {/* pipeline graph — the signature: color-coded flow, each stage its own hue */}
      <div className="overflow-x-auto pb-1">
        <svg viewBox={`0 0 ${vw} ${vh}`} className="min-w-[660px]" style={{ width: vw, maxWidth: "100%" }}
             role="img" aria-label="Model pipeline: each stage transforms the data toward a prediction">
          <defs>
            <filter id="sf-shadow" x="-20%" y="-20%" width="140%" height="160%">
              <feDropShadow dx="0" dy="1.5" stdDeviation="2" floodOpacity="0.18" />
            </filter>
            <style>{`
              .sf-flow { stroke-dasharray: 5 5; animation: sfflow .9s linear infinite; }
              @keyframes sfflow { to { stroke-dashoffset: -10; } }
              @media (prefers-reduced-motion: reduce) { .sf-flow { animation: none; stroke-dasharray: none; } }
            `}</style>
            {stages.map((s, i) => {
              const c = colorFor(s.key, i);
              return (
                <linearGradient key={i} id={`sf-ng${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lighten(c, 0.92)} />
                  <stop offset="100%" stopColor={lighten(c, 0.82)} />
                </linearGradient>
              );
            })}
            {stages.slice(0, -1).map((s, i) => {
              const c1 = colorFor(s.key, i), c2 = colorFor(stages[i + 1].key, i + 1);
              return (
                <g key={i}>
                  <linearGradient id={`sf-eg${i}`} gradientUnits="userSpaceOnUse"
                                  x1={nx(i) + NW} y1={cyN} x2={nx(i + 1)} y2={cyN}>
                    <stop offset="0%" stopColor={c1} />
                    <stop offset="100%" stopColor={c2} />
                  </linearGradient>
                  <marker id={`sf-m${i}`} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
                    <path d="M0,0 L7,3.5 L0,7 Z" fill={c2} />
                  </marker>
                </g>
              );
            })}
          </defs>

          {stages.slice(0, -1).map((_, i) => {
            const active = i + 1 < revealed;
            return (
              <line key={i} x1={nx(i) + NW} y1={cyN} x2={nx(i + 1) - 1} y2={cyN}
                    stroke={active ? `url(#sf-eg${i})` : "currentColor"}
                    className={active ? "sf-flow" : "text-slate-200 dark:text-slate-700"}
                    strokeWidth={active ? 2.5 : 1.5} strokeLinecap="round"
                    markerEnd={active ? `url(#sf-m${i})` : undefined} />
            );
          })}

          {stages.map((s, i) => {
            const shown = i < revealed;
            const isActive = i === active;
            const c = colorFor(s.key, i);
            return (
              <g key={s.key} onClick={() => setActive(i)} tabIndex={0}
                 onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setActive(i)}
                 className="cursor-pointer outline-none transition-transform duration-300"
                 style={{ transform: isActive ? "translateY(-2px)" : undefined }}>
                {isActive && (
                  <rect x={nx(i) - 3} y={ny - 3} width={NW + 6} height={NH + 6} rx={13}
                        fill="none" stroke={c} strokeWidth={2} opacity={0.55} />
                )}
                <rect x={nx(i)} y={ny} width={NW} height={NH} rx={11}
                      fill={shown ? `url(#sf-ng${i})` : "transparent"}
                      stroke={c} strokeOpacity={shown ? 0.35 : 0.3} strokeWidth={1.25}
                      filter={shown ? "url(#sf-shadow)" : undefined}
                      className={shown ? "" : "fill-white dark:fill-slate-900"} />
                <circle cx={nx(i) + 16} cy={ny + NH / 2} r={9}
                        fill={c} fillOpacity={shown ? 1 : 0.25} />
                <text x={nx(i) + 16} y={ny + NH / 2 + 3.5} textAnchor="middle"
                      fill={shown ? "#fff" : c} className="text-[10px] font-bold">{i + 1}</text>
                <text x={nx(i) + 30 + (NW - 38) / 2} y={ny + NH / 2 + 3.5} textAnchor="middle"
                      fill={c} className="text-[10px] font-bold">{s.title}</text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* detail panel for the active stage — accent bar in the stage's hue */}
      <div className="mt-4 flex overflow-hidden rounded-xl border border-slate-200 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-950/40">
        <div className="w-1.5 shrink-0" style={{ background: colorFor(cur.key, active) }} />
        <div className="flex-1 p-4">
          <div className="mb-1 text-xs font-bold uppercase tracking-wide" style={{ color: colorFor(cur.key, active) }}>
            Step {active + 1} · {cur.title}
          </div>
          <div className="mb-3 text-xs text-slate-500">{cur.summary}</div>
          <StageDetail stage={cur} accent={colorFor(cur.key, active)} />
        </div>
      </div>
    </div>
  );
}

function StageDetail({ stage, accent }: { stage: Stage; accent: string }) {
  if (stage.kind === "kv") {
    const rows = stage.data as { label: string; value: string | number }[];
    return (
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between gap-3 border-b border-slate-200/60 pb-1 text-sm dark:border-slate-800/60">
            <dt className="text-slate-500">{r.label}</dt>
            <dd className="max-w-[60%] truncate text-right font-medium text-slate-700 dark:text-slate-200" title={String(r.value)}>{String(r.value)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  if (stage.kind === "flags") {
    const flags = stage.data as { key: string; label: string; on: boolean }[];
    return (
      <div className="flex flex-wrap gap-2">
        {flags.map((f) => {
          const tone = FLAG_TONE[f.key] ?? "warn";
          const on = f.on;
          const cls = !on
            ? "border-slate-200 text-slate-400 dark:border-slate-700"
            : tone === "good"
            ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
            : "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300";
          return (
            <span key={f.key} className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${cls}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${on ? (tone === "good" ? "bg-emerald-500" : "bg-amber-500") : "bg-slate-300 dark:bg-slate-600"}`} />
              {f.label}
            </span>
          );
        })}
      </div>
    );
  }
  if (stage.kind === "vector") {
    const d = stage.data as { dims: number; values: number[]; note: string };
    return (
      <div>
        <div className="flex flex-wrap gap-1.5">
          {d.values.map((v, i) => (
            <span key={i} className="rounded-md bg-white px-2 py-1 font-mono text-xs text-slate-600 ring-1 ring-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:ring-slate-800">
              {v.toFixed(2)}
            </span>
          ))}
          <span className="rounded-md bg-slate-100 px-2 py-1 font-mono text-xs text-slate-400 dark:bg-slate-800">…{d.dims} dims</span>
        </div>
        <p className="mt-2 text-xs text-slate-400">{d.note}</p>
      </div>
    );
  }
  // bars (probabilities) and importance share a horizontal-bar rendering
  const items = stage.data as { label: string; value: number; active?: boolean }[];
  const max = Math.max(1e-9, ...items.map((i) => i.value));
  const isProb = stage.kind === "bars";
  return (
    <div className="space-y-2">
      {items.map((it) => {
        const pct = (it.value / max) * 100;
        const isSlate = isProb && !it.active;
        return (
          <div key={it.label} className="flex items-center gap-3 text-sm">
            <span className={`w-28 shrink-0 truncate text-right ${it.active ? "font-semibold text-slate-800 dark:text-slate-100" : "text-slate-500"}`} title={it.label}>{it.label}</span>
            <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800">
              <div className={`h-full rounded transition-all ${isSlate ? "bg-slate-300 dark:bg-slate-600" : ""}`}
                   style={{ width: `${pct}%`,
                            backgroundColor: isSlate ? undefined : accent,
                            opacity: !isProb && !it.active ? 0.6 : 1 }} />
            </div>
            <span className="w-16 shrink-0 text-right font-mono text-xs tabular-nums text-slate-400">
              {isProb ? `${(it.value * 100).toFixed(1)}%` : it.value.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
