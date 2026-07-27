import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api.js";
import CaseTable from "../components/CaseTable.jsx";

const STATUSES = ["", "needs_pa", "in_progress", "approved", "denied", "human_review"];

export default function Queue() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["cases", status, q],
    queryFn: () => api.listCases({ status: status || undefined, q: q || undefined }),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold">PA Queue</h1>
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search patient / procedure"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
          />
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm"
          >
            {STATUSES.map((s) => <option key={s} value={s}>{s ? s : "All statuses"}</option>)}
          </select>
        </div>
      </div>
      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error.message}</p>}
      {data && <CaseTable rows={data} />}
    </div>
  );
}
