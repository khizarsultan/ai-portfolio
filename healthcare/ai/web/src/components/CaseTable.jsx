import { useNavigate } from "react-router-dom";
import StatusBadge from "./StatusBadge.jsx";

function turnaround(created, updated) {
  const ms = new Date(updated) - new Date(created);
  if (ms < 1000) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  return m < 60 ? `${m}m` : `${Math.round(m / 60)}h`;
}

// Shared table for Queue and Review. `showReason` renders the escalation reason inline.
export default function CaseTable({ rows, showReason }) {
  const nav = useNavigate();
  if (!rows?.length) return <p className="py-10 text-center text-sm text-slate-400">No cases.</p>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">Patient</th>
            <th className="px-4 py-2">Procedure</th>
            <th className="px-4 py-2">Status</th>
            {showReason && <th className="px-4 py-2">Escalation reason</th>}
            <th className="px-4 py-2">Turnaround</th>
            <th className="px-4 py-2">Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr
              key={r.id}
              onClick={() => nav(`/cases/${r.id}`)}
              className="cursor-pointer hover:bg-slate-50"
            >
              <td className="px-4 py-2 font-medium text-slate-900">{r.patient_id}</td>
              <td className="px-4 py-2 text-slate-600">{r.procedure}</td>
              <td className="px-4 py-2"><StatusBadge status={r.status} /></td>
              {showReason && <td className="px-4 py-2 text-amber-700">{r.escalation_reason || "—"}</td>}
              <td className="px-4 py-2 text-slate-500">{turnaround(r.created_at, r.updated_at)}</td>
              <td className="px-4 py-2 text-slate-400">{new Date(r.updated_at).toLocaleTimeString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
