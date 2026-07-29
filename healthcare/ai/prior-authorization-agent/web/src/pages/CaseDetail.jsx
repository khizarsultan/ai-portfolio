import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getRole } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";
import Stepper from "../components/Stepper.jsx";

const TERMINAL = ["approved", "denied", "human_review"];
const canReview = () => ["reviewer", "admin"].includes(getRole());

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="text-sm text-slate-800">{children}</dd>
    </div>
  );
}

export default function CaseDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");

  const { data: c, isLoading } = useQuery({ queryKey: ["case", id], queryFn: () => api.getCase(id) });

  const mutate = (fn) =>
    useMutation({
      mutationFn: fn,
      onSuccess: (d) => { qc.setQueryData(["case", id], d); qc.invalidateQueries({ queryKey: ["cases"] }); setErr(""); },
      onError: (e) => setErr(e.message),
    });

  const runM = mutate(() => api.run(id));
  const approveM = mutate(() => api.approve(id));
  const sendBackM = mutate(() => api.sendBack(id, note));
  const escalateM = mutate(() => api.escalate(id, reason));
  const busy = runM.isPending || approveM.isPending || sendBackM.isPending || escalateM.isPending;

  if (isLoading || !c) return <p className="text-sm text-slate-400">Loading…</p>;

  return (
    <div className="space-y-6">
      <button onClick={() => nav(-1)} className="text-sm text-slate-500 hover:underline">← Back</button>

      {/* Patient + order summary */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold">{c.patient_id}</h1>
          <StatusBadge status={c.status} />
        </div>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Field label="Procedure">{c.order.cpt} — {c.order.display}</Field>
          <Field label="Plan">{c.plan_id}</Field>
          <Field label="Age / Sex">{c.patient.age} / {c.patient.sex}</Field>
          <Field label="Coverage">{c.patient.coverage_active ? "active" : "inactive"}</Field>
          <Field label="Diagnoses">{c.conditions.map((x) => x.code).join(", ") || "—"}</Field>
          <Field label="Notes">{c.notes || "—"}</Field>
        </dl>
      </section>

      {/* Status stepper */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Pipeline</h2>
        <Stepper steps={c.steps} current={c.current_step} terminal={TERMINAL.includes(c.status)} />
        {c.status === "needs_pa" && (
          <button
            onClick={() => runM.mutate()}
            disabled={busy}
            className="mt-4 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {runM.isPending ? "Running…" : "Run agent flow"}
          </button>
        )}
      </section>

      {/* Decision panel */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">Decision</h2>
          {c.trace_url && (
            <a href={c.trace_url} target="_blank" rel="noreferrer"
               className="text-xs font-medium text-blue-600 hover:underline">
              View full trace ↗
            </a>
          )}
        </div>
        {c.decision ? (
          <>
            <p className="mb-2 text-sm"><span className="font-medium">{c.decision}</span>{c.reason ? ` — ${c.reason}` : ""}</p>
            <pre className="whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-700">{c.rationale}</pre>
          </>
        ) : (
          <p className="text-sm text-slate-400">Not yet decided. Run the agent flow.</p>
        )}
      </section>

      {/* Action bar (role-gated) */}
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Actions</h2>
        {err && <p className="mb-3 text-sm text-red-600">{err}</p>}
        <div className="flex flex-wrap items-end gap-4">
          <button
            onClick={() => approveM.mutate()}
            disabled={busy || !canReview()}
            title={canReview() ? "" : "Reviewer or admin only"}
            className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            Approve
          </button>
          <div className="flex items-end gap-2">
            <div>
              <label className="block text-xs text-slate-500">Send back — note</label>
              <input value={note} onChange={(e) => setNote(e.target.value)}
                     className="rounded border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <button onClick={() => sendBackM.mutate()} disabled={busy}
                    className="rounded bg-slate-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">
              Send back
            </button>
          </div>
          <div className="flex items-end gap-2">
            <div>
              <label className="block text-xs text-slate-500">Escalate — reason</label>
              <input value={reason} onChange={(e) => setReason(e.target.value)}
                     className="rounded border border-slate-300 px-2 py-1 text-sm" />
            </div>
            <button onClick={() => escalateM.mutate()} disabled={busy || !canReview()}
                    title={canReview() ? "" : "Reviewer or admin only"}
                    className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">
              Escalate
            </button>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          All denials and escalations require a reviewer action before they are final.
        </p>
      </section>
    </div>
  );
}
