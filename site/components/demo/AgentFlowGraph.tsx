"use client";

// A real branching flowchart of the LangGraph agent topology (mirrors src/graph.py). The path
// taken on this run is highlighted and animates as steps reveal; click a visited node to open
// that agent's step. Hand-drawn SVG DAG — no external graph library.

type Step = { agent: string; status: string };
type Props = {
  steps: Step[];
  status: string;
  decision: { outcome: string } | null;
  needsPa: boolean | null;
  coverageOk: boolean | null;
  revealCount: number;
  onPick?: (agent: string) => void;
};

const W = 120, H = 38;
type Node = { key: string; label: string; x: number; y: number; agent?: string; terminal?: boolean };
const NODES: Node[] = [
  { key: "intake", label: "Intake", x: 270, y: 14 },
  { key: "checker", label: "Checker", x: 270, y: 82, agent: "Checker" },
  { key: "autoclear", label: "Auto-cleared", x: 470, y: 82, terminal: true },
  { key: "verifier", label: "Verifier", x: 270, y: 150, agent: "Verifier" },
  { key: "humanreview", label: "Human review", x: 470, y: 175, terminal: true },
  { key: "assembler", label: "Assembler", x: 270, y: 222, agent: "Assembler" },
  { key: "submitter", label: "Submitter", x: 270, y: 300, agent: "Submitter" },
  { key: "approved", label: "Approved", x: 470, y: 300, terminal: true },
  { key: "appealer", label: "Appealer", x: 80, y: 300, agent: "Appealer" },
];
const N: Record<string, Node> = Object.fromEntries(NODES.map((n) => [n.key, n]));
const cx = (n: Node) => n.x + W / 2;
const cy = (n: Node) => n.y + H / 2;

export default function AgentFlowGraph({ steps, status, decision, needsPa, coverageOk, revealCount, onPick }: Props) {
  const shown = steps.slice(0, revealCount);
  const seen = new Set(shown.map((s) => s.agent));
  const done = revealCount >= steps.length;
  const hadNeedsInfo = steps.some((s) => s.status === "needs_info");
  const hadDenied = steps.some((s) => s.status === "denied");

  // terminal nodes light only once the run is complete
  const on = (key: string): boolean => {
    const node = N[key];
    if (node.agent) return seen.has(node.agent);
    if (key === "intake") return revealCount >= 1;
    if (!done) return false;
    if (key === "autoclear") return needsPa === false;
    if (key === "approved") return decision?.outcome === "APPROVED";
    if (key === "humanreview") return status === "human_review";
    return false;
  };

  const edges: { from: string; to: string; label?: string; dashed?: boolean; d?: string }[] = [
    { from: "intake", to: "checker" },
    { from: "checker", to: "autoclear", label: "no PA" },
    { from: "checker", to: "verifier", label: "PA" },
    { from: "verifier", to: "humanreview", label: "not covered" },
    { from: "verifier", to: "assembler", label: "covered" },
    { from: "assembler", to: "submitter" },
    { from: "submitter", to: "approved", label: "APPROVED" },
    { from: "submitter", to: "appealer", label: "DENIED" },
    { from: "appealer", to: "submitter" },
    { from: "submitter", to: "assembler", label: "NEEDS_INFO",
      d: "M 288,300 C 210,270 210,252 270,246" },
    { from: "submitter", to: "humanreview", label: "cap", dashed: true,
      d: "M 390,306 C 452,300 470,250 470,213" },
  ];

  const edgeOn = (e: { from: string; to: string }): boolean => {
    if (e.to === "assembler" && e.from === "submitter") return hadNeedsInfo && seen.has("Assembler");
    if (e.to === "appealer") return seen.has("Appealer");
    if (e.from === "appealer") return seen.has("Appealer");
    if (e.to === "humanreview" && e.from === "submitter") return done && status === "human_review" && coverageOk !== false;
    if (e.to === "humanreview" && e.from === "verifier") return done && status === "human_review" && coverageOk === false;
    if (e.to === "autoclear") return on("autoclear");
    if (e.to === "approved") return on("approved");
    return on(e.from) && on(e.to);
  };

  // straight-edge anchor points (from → to), chosen by relative position
  function anchors(a: Node, b: Node) {
    if (Math.abs(cy(a) - cy(b)) < 4) {
      return b.x > a.x ? { x1: a.x + W, y1: cy(a), x2: b.x, y2: cy(b) }
                       : { x1: a.x, y1: cy(a), x2: b.x + W, y2: cy(b) };
    }
    if (b.y > a.y) {
      // going down (possibly diagonal)
      const x1 = b.x > a.x + W ? a.x + W : cx(a);
      return { x1, y1: b.x > a.x + W ? cy(a) : a.y + H, x2: b.x > a.x + W ? b.x : cx(b), y2: b.x > a.x + W ? cy(b) : b.y };
    }
    return { x1: cx(a), y1: a.y, x2: cx(b), y2: b.y + H };
  }

  return (
    <svg viewBox="0 0 620 360" className="w-full" style={{ maxWidth: 620 }}>
      <defs>
        <marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" className="fill-slate-300 dark:fill-slate-600" />
        </marker>
        <marker id="arOn" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" className="fill-brand" />
        </marker>
      </defs>

      {edges.map((e, i) => {
        const active = edgeOn(e);
        const a = N[e.from], b = N[e.to];
        const stroke = active ? "stroke-brand" : "stroke-slate-200 dark:stroke-slate-700";
        const mk = active ? "url(#arOn)" : "url(#ar)";
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
