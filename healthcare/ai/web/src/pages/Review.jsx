import { useQuery } from "@tanstack/react-query";
import { api } from "../api.js";
import CaseTable from "../components/CaseTable.jsx";

// Same table, filtered to human_review, with the escalation reason shown inline (planv3 C3.3).
export default function Review() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cases", "human_review"],
    queryFn: () => api.listCases({ status: "human_review" }),
  });
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Review queue — human review required</h1>
      {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error.message}</p>}
      {data && <CaseTable rows={data} showReason />}
    </div>
  );
}
