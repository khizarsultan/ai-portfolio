// Status-driven color coding shared by the queue and detail screens.
const STYLES = {
  needs_pa: "bg-slate-100 text-slate-700 ring-slate-300",
  in_progress: "bg-blue-100 text-blue-700 ring-blue-300",
  approved: "bg-green-100 text-green-700 ring-green-300",
  denied: "bg-red-100 text-red-700 ring-red-300",
  human_review: "bg-amber-100 text-amber-800 ring-amber-300",
};
const LABELS = {
  needs_pa: "Needs PA",
  in_progress: "In progress",
  approved: "Approved",
  denied: "Denied",
  human_review: "Human review",
};

export default function StatusBadge({ status }) {
  const cls = STYLES[status] || "bg-slate-100 text-slate-700 ring-slate-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}>
      {LABELS[status] || status}
    </span>
  );
}
