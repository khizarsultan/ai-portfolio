import { Card } from "./ui";

// The four client-facing trust pillars. `checks` are the standing controls (same every run);
// `evidence` is derived per run by the backend so clients see the controls actually firing.
export type Pillar = {
  key: string;
  title: string;
  subtitle: string;
  checks: { label: string; detail: string; enforced: boolean }[];
  evidence: { label: string; value: string }[];
};

// Accent per pillar — matches the demo's Tailwind palette (light + dark).
const ACCENT: Record<string, { dot: string; text: string; ring: string }> = {
  safety: { dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", ring: "ring-emerald-400/30" },
  security: { dot: "bg-brand", text: "text-brand", ring: "ring-brand/30" },
  guardrails: { dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400", ring: "ring-amber-400/30" },
  audit: { dot: "bg-slate-500", text: "text-slate-600 dark:text-slate-300", ring: "ring-slate-400/30" },
};

export default function GovernancePanel({ pillars }: { pillars: Pillar[] }) {
  if (!pillars?.length) return null;
  return (
    <Card>
      <h2 className="text-sm font-semibold text-slate-500">AI safety, security, guardrails &amp; compliance</h2>
      <p className="mt-1 text-xs text-slate-400">
        The trust controls enforced on every run — with evidence from this run.
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {pillars.map((p) => {
          const a = ACCENT[p.key] ?? ACCENT.audit;
          return (
            <div
              key={p.key}
              className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"
            >
              <div className="flex items-start gap-2.5">
                <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ring-4 ${a.dot} ${a.ring}`} />
                <div>
                  <h3 className={`text-sm font-bold ${a.text}`}>{p.title}</h3>
                  <p className="text-[11px] text-slate-400">{p.subtitle}</p>
                </div>
              </div>

              <ul className="mt-3 space-y-1.5">
                {p.checks.map((c) => (
                  <li key={c.label} className="flex gap-2 text-[13px]" title={c.detail}>
                    <span className={`mt-0.5 shrink-0 font-bold ${a.text}`} aria-hidden>✓</span>
                    <span className="text-slate-700 dark:text-slate-200">{c.label}</span>
                  </li>
                ))}
              </ul>

              {p.evidence.length > 0 && (
                <dl className="mt-3 space-y-1 border-t border-slate-100 pt-3 dark:border-slate-800">
                  {p.evidence.map((e) => (
                    <div key={e.label} className="flex items-baseline justify-between gap-3 text-[11px]">
                      <dt className="text-slate-400">{e.label}</dt>
                      <dd className="text-right font-medium tabular-nums text-slate-700 dark:text-slate-200">{e.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
