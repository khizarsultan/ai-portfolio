"use client";
// Lightweight dependency-free SVG charts for the v2 dashboards. No chart lib —
// matches the site's existing hand-rolled SVG approach (StageFlow, flow graphs)
// and keeps the client bundle tiny. All theme-aware via Tailwind currentColor.
import { ReactNode } from "react";

export const C = {
  brand: "#2a78d6", aqua: "#0ea5b7", pos: "#ef4444", neg: "#3b82f6",
  good: "#16a34a", warn: "#d97706", crit: "#dc2626", muted: "#94a3b8", grid: "#e2e8f0",
};

// ---- metric tile ----
export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "good" | "warn" | "crit" }) {
  const color = tone === "good" ? "text-emerald-600 dark:text-emerald-400"
    : tone === "warn" ? "text-amber-600 dark:text-amber-400"
    : tone === "crit" ? "text-red-600 dark:text-red-400" : "text-slate-900 dark:text-slate-100";
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 dark:border-slate-800 dark:bg-slate-950/50" title={hint}>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-0.5 text-xl font-bold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  const s = status.toUpperCase();
  const cls = s === "OK" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
    : s.startsWith("WARN") ? "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
    : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>{s}</span>;
}

type Pt = [number, number];
type Series = { points: Pt[]; color?: string; dashed?: boolean; name?: string };

// ---- generic line chart (ROC / PR / what-if) ----
export function LineChart({
  series, xLabel, yLabel, xDomain, yDomain, height = 260, hlines = [], markers = [],
}: {
  series: Series[]; xLabel?: string; yLabel?: string;
  xDomain?: [number, number]; yDomain?: [number, number]; height?: number;
  hlines?: { y: number; label?: string; color?: string }[];
  markers?: { x: number; y: number; color?: string; label?: string }[];
}) {
  const W = 480, H = height, pad = { l: 46, r: 14, t: 12, b: 34 };
  const all = series.flatMap((s) => s.points);
  const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
  const [x0, x1] = xDomain ?? [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = yDomain ?? [Math.min(...ys), Math.max(...ys)];
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (y: number) => H - pad.b - ((y - y0) / (y1 - y0 || 1)) * (H - pad.t - pad.b);
  const ticks = (a: number, b: number, n = 4) => Array.from({ length: n + 1 }, (_, i) => a + ((b - a) * i) / n);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img">
      {ticks(y0, y1).map((t, i) => (
        <g key={`y${i}`}>
          <line x1={pad.l} y1={sy(t)} x2={W - pad.r} y2={sy(t)} stroke={C.grid} strokeWidth={1} className="dark:opacity-20" />
          <text x={pad.l - 6} y={sy(t) + 3} textAnchor="end" fontSize={10} fill={C.muted}>{(+t).toFixed(2)}</text>
        </g>
      ))}
      {ticks(x0, x1).map((t, i) => (
        <text key={`x${i}`} x={sx(t)} y={H - pad.b + 14} textAnchor="middle" fontSize={10} fill={C.muted}>{(+t).toFixed(x1 - x0 <= 1 ? 2 : 0)}</text>
      ))}
      {hlines.map((h, i) => (
        <line key={`h${i}`} x1={pad.l} y1={sy(h.y)} x2={W - pad.r} y2={sy(h.y)} stroke={h.color ?? C.muted} strokeWidth={1} strokeDasharray="4 3" />
      ))}
      {series.map((s, i) => (
        <polyline key={i} fill="none" stroke={s.color ?? C.brand} strokeWidth={2}
          strokeDasharray={s.dashed ? "5 4" : undefined}
          points={s.points.map((p) => `${sx(p[0])},${sy(p[1])}`).join(" ")} />
      ))}
      {markers.map((mk, i) => (
        <circle key={i} cx={sx(mk.x)} cy={sy(mk.y)} r={5} fill={mk.color ?? C.crit} stroke="#fff" strokeWidth={2} />
      ))}
      {yLabel && <text x={12} y={H / 2} fontSize={10} fill={C.muted} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle">{yLabel}</text>}
      {xLabel && <text x={(W + pad.l) / 2} y={H - 4} fontSize={10} fill={C.muted} textAnchor="middle">{xLabel}</text>}
    </svg>
  );
}

// ---- confusion matrix 2x2 ----
export function ConfusionMatrix({ cm }: { cm: number[][] }) {
  const flat = cm.flat(); const max = Math.max(...flat, 1);
  const cells = [
    { r: 0, c: 0, v: cm[0][0], lab: "True neg" }, { r: 0, c: 1, v: cm[0][1], lab: "False pos" },
    { r: 1, c: 0, v: cm[1][0], lab: "False neg" }, { r: 1, c: 1, v: cm[1][1], lab: "True pos" },
  ];
  const W = 300, H = 220, ox = 70, oy = 24, cw = 100, ch = 78;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      <text x={ox + cw} y={14} textAnchor="middle" fontSize={11} fill={C.muted}>Predicted</text>
      <text x={ox - 52} y={oy + ch} textAnchor="middle" fontSize={11} fill={C.muted} transform={`rotate(-90 ${ox - 52} ${oy + ch})`}>Actual</text>
      {["No", "Yes"].map((t, i) => <text key={t} x={ox + i * cw + cw / 2} y={oy - 4} textAnchor="middle" fontSize={10} fill={C.muted}>{t}</text>)}
      {["No", "Yes"].map((t, i) => <text key={t} x={ox - 8} y={oy + i * ch + ch / 2} textAnchor="end" fontSize={10} fill={C.muted}>{t}</text>)}
      {cells.map((cell) => {
        const good = (cell.r === cell.c);
        const alpha = 0.15 + 0.55 * (cell.v / max);
        return (
          <g key={cell.lab}>
            <rect x={ox + cell.c * cw} y={oy + cell.r * ch} width={cw - 4} height={ch - 4} rx={8}
              fill={good ? C.brand : C.pos} opacity={alpha} />
            <text x={ox + cell.c * cw + cw / 2 - 2} y={oy + cell.r * ch + ch / 2 - 4} textAnchor="middle" fontSize={18} fontWeight={700} fill="currentColor" className="text-slate-800 dark:text-slate-100">{cell.v.toLocaleString()}</text>
            <text x={ox + cell.c * cw + cw / 2 - 2} y={oy + cell.r * ch + ch / 2 + 12} textAnchor="middle" fontSize={9} fill={C.muted}>{cell.lab}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ---- NxN heatmap (multiclass confusion, row-normalized) ----
export function Heatmap({ matrix, labels }: { matrix: number[][]; labels: string[] }) {
  const n = labels.length, cell = 62, ox = 78, oy = 46;
  const W = ox + n * cell + 8, H = oy + n * cell + 16;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      <text x={ox + (n * cell) / 2} y={14} textAnchor="middle" fontSize={11} fill={C.muted}>Predicted →</text>
      <text x={16} y={oy + (n * cell) / 2} textAnchor="middle" fontSize={11} fill={C.muted} transform={`rotate(-90 16 ${oy + (n * cell) / 2})`}>True →</text>
      {labels.map((l, i) => (
        <text key={`c${l}`} x={ox + i * cell + cell / 2} y={oy - 6} textAnchor="middle" fontSize={9} fill={C.muted}>{l}</text>
      ))}
      {labels.map((l, i) => (
        <text key={`r${l}`} x={ox - 6} y={oy + i * cell + cell / 2 + 3} textAnchor="end" fontSize={9} fill={C.muted}>{l}</text>
      ))}
      {matrix.map((row, r) => row.map((v, c) => (
        <g key={`${r}-${c}`}>
          <rect x={ox + c * cell} y={oy + r * cell} width={cell - 3} height={cell - 3} rx={6}
            fill={r === c ? C.good : C.crit} opacity={0.12 + 0.7 * v} />
          <text x={ox + c * cell + (cell - 3) / 2} y={oy + r * cell + (cell - 3) / 2 + 4} textAnchor="middle"
            fontSize={12} fontWeight={600} fill="currentColor" className="text-slate-700 dark:text-slate-100">{(v * 100).toFixed(0)}%</text>
        </g>
      )))}
    </svg>
  );
}

// ---- colored horizontal value bars (class probabilities) ----
export function ColorBars({ items }: { items: { label: string; value: number; color: string; active?: boolean }[] }) {
  const m = Math.max(1e-9, ...items.map((i) => i.value));
  return (
    <div className="space-y-1.5">
      {items.map((it) => (
        <div key={it.label} className={`flex items-center gap-2 text-sm ${it.active ? "font-semibold" : ""}`}>
          <span className="w-24 shrink-0 truncate text-right text-slate-500">{it.label}</span>
          <div className="relative h-4 flex-1 rounded bg-slate-100 dark:bg-slate-800">
            <div className="h-full rounded" style={{ width: `${(it.value / m) * 100}%`, background: it.color }} />
          </div>
          <span className="w-12 shrink-0 tabular-nums text-slate-400">{(it.value * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

// ---- histogram with vertical markers ----
export function Histogram({ edges, counts, markers = [], xLabel }: {
  edges: number[]; counts: number[]; xLabel?: string;
  markers?: { x: number; color: string; label: string }[];
}) {
  const W = 480, H = 240, pad = { l: 40, r: 12, t: 12, b: 30 };
  const x0 = edges[0], x1 = edges[edges.length - 1], maxC = Math.max(...counts, 1);
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (c: number) => H - pad.b - (c / maxC) * (H - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      {counts.map((c, i) => {
        const xa = sx(edges[i]), xb = sx(edges[i + 1]);
        return <rect key={i} x={xa} y={sy(c)} width={Math.max(1, xb - xa - 1)} height={H - pad.b - sy(c)} fill={C.brand} opacity={0.7} />;
      })}
      {markers.map((mk, i) => (
        <g key={i}>
          <line x1={sx(mk.x)} y1={pad.t} x2={sx(mk.x)} y2={H - pad.b} stroke={mk.color} strokeWidth={1.5} strokeDasharray="4 3" />
          <text x={sx(mk.x)} y={pad.t + 8} fontSize={9} fill={mk.color} textAnchor="middle">{mk.label}</text>
        </g>
      ))}
      {xLabel && <text x={W / 2} y={H - 4} fontSize={10} fill={C.muted} textAnchor="middle">{xLabel}</text>}
    </svg>
  );
}

// ---- grouped bars (champion vs challenger) ----
export function GroupedBars({ groups, series }: {
  groups: string[]; series: { name: string; color: string; values: number[] }[];
}) {
  const W = 480, H = 260, pad = { l: 36, r: 12, t: 24, b: 30 };
  const gw = (W - pad.l - pad.r) / groups.length;
  const bw = (gw * 0.7) / series.length;
  const sy = (v: number) => H - pad.b - v * (H - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={pad.l} y1={sy(t)} x2={W - pad.r} y2={sy(t)} stroke={C.grid} strokeWidth={1} className="dark:opacity-20" />
          <text x={pad.l - 5} y={sy(t) + 3} textAnchor="end" fontSize={9} fill={C.muted}>{t}</text>
        </g>
      ))}
      {groups.map((g, gi) => (
        <g key={g}>
          {series.map((s, si) => {
            const x = pad.l + gi * gw + gw * 0.15 + si * bw;
            return <rect key={s.name} x={x} y={sy(s.values[gi])} width={bw - 2} height={H - pad.b - sy(s.values[gi])} fill={s.color} rx={2} />;
          })}
          <text x={pad.l + gi * gw + gw / 2} y={H - pad.b + 13} textAnchor="middle" fontSize={9} fill={C.muted}>{g}</text>
        </g>
      ))}
      {series.map((s, i) => (
        <g key={s.name}>
          <rect x={pad.l + i * 110} y={6} width={10} height={10} rx={2} fill={s.color} />
          <text x={pad.l + i * 110 + 14} y={15} fontSize={10} fill={C.muted}>{s.name}</text>
        </g>
      ))}
    </svg>
  );
}

// ---- segmented stacked bar (outcome breakdown) ----
export function StackedBar({ segments, unit = "" }: { segments: { label: string; value: number; color: string }[]; unit?: string }) {
  const tot = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div>
      <div className="flex h-9 w-full overflow-hidden rounded-lg ring-1 ring-slate-200 dark:ring-slate-800">
        {segments.map((s) => (
          <div key={s.label} style={{ width: `${(s.value / tot) * 100}%`, background: s.color }}
            className="flex items-center justify-center text-[11px] font-semibold text-white" title={`${s.label}: ${s.value.toFixed(0)}`}>
            {s.value / tot > 0.06 ? s.value.toFixed(0) : ""}
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {segments.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5 text-slate-500">
            <span className="h-3 w-3 rounded-sm" style={{ background: s.color }} />{s.label} <strong className="tabular-nums text-slate-700 dark:text-slate-200">{s.value.toFixed(0)}{unit}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

// ---- radial progress ring (generic 0..1 metric) ----
export function Ring({ value, label, color = C.brand }: { value: number; label: string; color?: string }) {
  const r = 34, circ = 2 * Math.PI * r, off = circ * (1 - Math.max(0, Math.min(1, value)));
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 90 90" className="h-24 w-24">
        <circle cx={45} cy={45} r={r} fill="none" stroke={C.grid} strokeWidth={9} className="dark:opacity-30" />
        <circle cx={45} cy={45} r={r} fill="none" stroke={color} strokeWidth={9} strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={off} transform="rotate(-90 45 45)" />
        <text x={45} y={50} textAnchor="middle" fontSize={17} fontWeight={700} fill={color}>{Math.round(value * 100)}%</text>
      </svg>
      <span className="mt-1 text-center text-xs text-slate-500">{label}</span>
    </div>
  );
}

// ---- radial gauge (0..100%) ----
export function Gauge({ value, threshold, danger }: { value: number; threshold?: number; danger?: boolean }) {
  const pct = Math.max(0, Math.min(1, value));
  const W = 220, H = 130, cx = W / 2, cy = 118, r = 90;
  const ang = (t: number) => Math.PI * (1 - t); // t 0..1 -> pi..0
  const pt = (t: number, rr = r) => [cx + rr * Math.cos(ang(t)), cy - rr * Math.sin(ang(t))];
  const arc = (a: number, b: number, rr = r) => {
    const [x1, y1] = pt(a, rr), [x2, y2] = pt(b, rr);
    return `M ${x1} ${y1} A ${rr} ${rr} 0 0 1 ${x2} ${y2}`;
  };
  const col = danger ? C.crit : C.good;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-[220px]">
      <path d={arc(0, 1)} fill="none" stroke={C.grid} strokeWidth={14} strokeLinecap="round" className="dark:opacity-30" />
      <path d={arc(0, pct)} fill="none" stroke={col} strokeWidth={14} strokeLinecap="round" />
      {threshold != null && <line x1={pt(threshold, r - 12)[0]} y1={pt(threshold, r - 12)[1]} x2={pt(threshold, r + 12)[0]} y2={pt(threshold, r + 12)[1]} stroke="currentColor" strokeWidth={2} className="text-slate-700 dark:text-slate-200" />}
      <text x={cx} y={cy - 20} textAnchor="middle" fontSize={30} fontWeight={800} fill={col}>{(pct * 100).toFixed(1)}%</text>
      <text x={cx} y={cy - 2} textAnchor="middle" fontSize={10} fill={C.muted}>predicted risk</text>
    </svg>
  );
}
