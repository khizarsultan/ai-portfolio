"use client";

// A real flowchart of the clinical-documentation agent topology (mirrors src/graph.py): a
// linear draft-then-validate pipeline with a MANDATORY sign-off gate. The path taken on this
// run is highlighted and animates as steps reveal; click a visited node to open that agent's
// step. Hand-drawn SVG DAG — no external graph library.

type Step = { agent: string; status: string };
type Props = {
  steps: Step[];
  status: string;
  revealCount: number;
  onPick?: (agent: string) => void;
};

const W = 124, H = 38;
type Node = { key: string; label: string; x: number; y: number; agent?: string; terminal?: boolean };
const NODES: Node[] = [
  { key: "intake", label: "Intake", x: 228, y: 8, agent: "Intake" },
  { key: "soap", label: "SOAP Writer", x: 228, y: 74, agent: "SOAP Writer" },
  { key: "coder", label: "Coder", x: 228, y: 140, agent: "Coder" },
  { key: "validator", label: "Validator", x: 228, y: 206, agent: "Validator" },
  { key: "humanreview", label: "Human review", x: 440, y: 206, terminal: true },
  { key: "signoff", label: "Sign-off (gate)", x: 228, y: 272, agent: "Sign-off" },
  { key: "recorder", label: "Recorder", x: 228, y: 338, agent: "Recorder" },
  { key: "recorded", label: "Recorded", x: 440, y: 338, terminal: true },
];
const N: Record<string, Node> = Object.fromEntries(NODES.map((n) => [n.key, n]));
const cx = (n: Node) => n.x + W / 2;
const cy = (n: Node) => n.y + H / 2;

export default function ClinicalFlowGraph({ steps, status, revealCount, onPick }: Props) {
  const shown = steps.slice(0, revealCount);
  const seen = new Set(shown.map((s) => s.agent));
  const done = revealCount >= steps.length;
  const signoffSeen = seen.has("Sign-off");
  const edited = shown.filter((s) => s.agent === "SOAP Writer").length > 1;

  const on = (key: string): boolean => {
    const node = N[key];
    if (node.agent) return seen.has(node.agent);
    if (!done) return false;
    if (key === "recorded") return status === "recorded";
    if (key === "humanreview") return status === "human_review";
    return false;
  };

  const edges: { from: string; to: string; label?: string; dashed?: boolean; d?: string }[] = [
    { from: "intake", to: "soap" },
    { from: "soap", to: "coder" },
    { from: "coder", to: "validator" },
    { from: "validator", to: "humanreview", label: "flags" },
    { from: "validator", to: "signoff", label: "clean" },
    { from: "signoff", to: "recorder", label: "signed" },
    { from: "recorder", to: "recorded", label: "written" },
    { from: "signoff", to: "humanreview", label: "rejected", dashed: true,
      d: "M 352,284 C 430,272 452,250 452,244" },
    { from: "signoff", to: "soap", label: "edit", dashed: true,
      d: "M 226,286 C 150,270 150,110 226,96" },
  ];

  const edgeOn = (e: { from: string; to: string }): boolean => {
    if (e.to === "humanreview" && e.from === "validator")
      return done && status === "human_review" && !signoffSeen;
    if (e.to === "humanreview" && e.from === "signoff")
      return done && status === "human_review" && signoffSeen;
    if (e.from === "signoff" && e.to === "soap") return edited;
    if (e.to === "recorder") return seen.has("Recorder");
    if (e.to === "recorded") return on("recorded");
    if (e.to === "signoff") return signoffSeen;
    return on(e.from) && on(e.to);
  };

  function anchors(a: Node, b: Node) {
    if (Math.abs(cy(a) - cy(b)) < 4) {
      return b.x > a.x ? { x1: a.x + W, y1: cy(a), x2: b.x, y2: cy(b) }
                       : { x1: a.x, y1: cy(a), x2: b.x + W, y2: cy(b) };
    }
    return { x1: cx(a), y1: a.y + H, x2: cx(b), y2: b.y };
  }

  return (
    <svg viewBox="0 0 600 392" className="w-full" style={{ maxWidth: 600 }}>
      <defs>
        <marker id="car" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" className="fill-slate-300 dark:fill-slate-600" />
        </marker>
        <marker id="carOn" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" className="fill-brand" />
        </marker>
      </defs>

      {edges.map((e, i) => {
        const active = edgeOn(e);
        const a = N[e.from], b = N[e.to];
        const stroke = active ? "stroke-brand" : "stroke-slate-200 dark:stroke-slate-700";
        const mk = active ? "url(#carOn)" : "url(#car)";
        let mid: { x: number; y: number };
        let el;
        if (e.d) {
          el = <path d={e.d} fill="none" className={stroke} strokeWidth={active ? 2 : 1.5}
                     strokeDasharray={e.dashed ? "4 3" : undefined} markerEnd={mk} />;
          const m = e.d.match(/C\s*([\d.]+),([\d.]+)/);
          mid = m ? { x: +m[1], y: +m[2] } : { x: cx(a), y: cy(a) };
        } else {
          const p = anchors(a, b);
          el = <line x1={p.x1} y1={p.y1} x2={p.x2} y2={p.y2} className={stroke}
                     strokeWidth={active ? 2 : 1.5} markerEnd={mk} />;
          mid = { x: (p.x1 + p.x2) / 2, y: (p.y1 + p.y2) / 2 };
        }
        return (
          <g key={i} className="transition-all duration-300">
            {el}
            {e.label && (
              <>
                <rect x={mid.x - e.label.length * 2.7 - 3} y={mid.y - 12} width={e.label.length * 5.4 + 6}
                      height={12} rx={3} className="fill-white dark:fill-slate-950" />
                <text x={mid.x} y={mid.y - 3} textAnchor="middle"
                      className={`text-[9px] font-semibold ${active ? "fill-brand" : "fill-slate-400"}`}>{e.label}</text>
              </>
            )}
          </g>
        );
      })}

      {NODES.map((n) => {
        const active = on(n.key);
        const clickable = !!n.agent && seen.has(n.agent);
        const fill = active
          ? n.terminal
            ? status === "human_review" && n.key === "humanreview"
              ? "fill-orange-500" : "fill-emerald-500"
            : "fill-brand"
          : "fill-white dark:fill-slate-900";
        const textCls = active ? "fill-white" : "fill-slate-400";
        const strokeCls = active ? "stroke-transparent" : "stroke-slate-200 dark:stroke-slate-700";
        return (
          <g key={n.key} onClick={() => clickable && n.agent && onPick?.(n.agent)}
             className={`transition-all duration-300 ${clickable ? "cursor-pointer" : ""}`}>
            <rect x={n.x} y={n.y} width={W} height={H} rx={8}
                  className={`${fill} ${strokeCls}`} strokeWidth={1.5} />
            <text x={cx(n)} y={cy(n) + 3.5} textAnchor="middle"
                  className={`text-[11px] font-semibold ${textCls}`}>{n.label}</text>
          </g>
        );
      })}
    </svg>
  );
}
