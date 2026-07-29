// Simple horizontal pipeline stepper. Steps before/at current_step are done/current;
// the rest are pending. (Rich per-step reasoning is deferred — planv3 C6.)
export default function Stepper({ steps, current, terminal }) {
  const idx = current ? steps.indexOf(current) : -1;
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {steps.map((step, i) => {
        let state = "pending";
        if (idx >= 0) {
          if (i < idx || terminal) state = "done";
          else if (i === idx) state = "current";
        }
        const dot = {
          done: "bg-green-500 text-white",
          current: "bg-blue-600 text-white ring-4 ring-blue-200",
          pending: "bg-slate-200 text-slate-500",
        }[state];
        return (
          <li key={step} className="flex items-center gap-2">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${dot}`}>
              {i + 1}
            </span>
            <span className={`text-sm ${state === "pending" ? "text-slate-400" : "text-slate-800"}`}>
              {step}
            </span>
            {i < steps.length - 1 && <span className="mx-1 h-px w-6 bg-slate-300" />}
          </li>
        );
      })}
    </ol>
  );
}
