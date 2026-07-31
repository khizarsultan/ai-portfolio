"use client";
// v2 shell: three stakeholder views over one precomputed dataset —
// Executive Summary (business), Model + Explainability (XAI), MLOps Pipeline.
// Data is a static JSON built offline (precompute_demo.py); the live predict
// inside the Model tab still calls the /api/diabetes serverless function.
import { useEffect, useState } from "react";
import { getJSON } from "./ui";
import type { DemoData } from "./diabetes/types";
import Executive from "./diabetes/Executive";
import ModelDash from "./diabetes/ModelDash";
import MLOps from "./diabetes/MLOps";

const TABS = ["Executive Summary", "Model + Explainability", "MLOps Pipeline"] as const;
type Tab = typeof TABS[number];

export default function DiabetesDemo() {
  const [tab, setTab] = useState<Tab>("Model + Explainability");
  const [d, setD] = useState<DemoData | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    getJSON<DemoData>("/demo-data/diabetes.json").then(setD).catch((e) => setErr((e as Error).message));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3 dark:border-slate-800">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${tab === t ? "bg-brand text-white shadow-sm" : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"}`}>
            {t}
          </button>
        ))}
      </div>
      {err && <p className="text-sm text-red-500">Could not load dashboard data: {err}</p>}
      {!d && !err && <p className="text-sm text-slate-400">Loading dashboard…</p>}
      {d && tab === "Executive Summary" && <Executive d={d} />}
      {d && tab === "Model + Explainability" && <ModelDash d={d} />}
      {d && tab === "MLOps Pipeline" && <MLOps d={d} />}
    </div>
  );
}
