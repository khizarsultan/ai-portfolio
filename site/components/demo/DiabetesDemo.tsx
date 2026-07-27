"use client";
import { useState } from "react";
import { postJSON, Card, Label, TextInput, Select, RunButton, ErrorNote, DevHint, Verdict, ProbabilityBar, Bars } from "./ui";
import { prettyFeature } from "./features";

type Result = {
  probability: number; threshold: number; flag: boolean; label: string;
  global_importance: { feature: string; importance: number }[];
};

const DEFAULTS = {
  gender: "Female", age: 54, bmi: 28.5, HbA1c_level: 6.2, blood_glucose_level: 140,
  smoking_history: "never", hypertension: 0, heart_disease: 0,
};

export default function DiabetesDemo() {
  const [f, setF] = useState<Record<string, string | number>>({ ...DEFAULTS });
  const [res, setRes] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const set = (k: string, v: string | number) => setF((s) => ({ ...s, [k]: v }));

  async function run() {
    setLoading(true); setErr(""); setRes(null);
    try {
      setRes(await postJSON<Result>("/api/diabetes", f));
    } catch (e) { setErr((e as Error).message); }
    finally { setLoading(false); }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <h2 className="mb-4 text-lg font-semibold">Patient</h2>
        <div className="grid grid-cols-2 gap-4">
          <div><Label>Gender</Label>
            <Select value={f.gender} onChange={(e) => set("gender", e.target.value)}>
              {["Female", "Male", "Other"].map((o) => <option key={o}>{o}</option>)}
            </Select></div>
          <div><Label>Age</Label>
            <TextInput type="number" min={1} max={100} value={f.age} onChange={(e) => set("age", +e.target.value)} /></div>
          <div><Label>BMI</Label>
            <TextInput type="number" step={0.1} value={f.bmi} onChange={(e) => set("bmi", +e.target.value)} /></div>
          <div><Label>HbA1c level (%)</Label>
            <TextInput type="number" step={0.1} value={f.HbA1c_level} onChange={(e) => set("HbA1c_level", +e.target.value)} /></div>
          <div><Label>Blood glucose (mg/dL)</Label>
            <TextInput type="number" value={f.blood_glucose_level} onChange={(e) => set("blood_glucose_level", +e.target.value)} /></div>
          <div><Label>Smoking history</Label>
            <Select value={f.smoking_history} onChange={(e) => set("smoking_history", e.target.value)}>
              {["never", "former", "current", "ever", "not current", "unknown"].map((o) => <option key={o}>{o}</option>)}
            </Select></div>
          <div><Label>Hypertension</Label>
            <Select value={f.hypertension} onChange={(e) => set("hypertension", +e.target.value)}>
              <option value={0}>No</option><option value={1}>Yes</option>
            </Select></div>
          <div><Label>Heart disease</Label>
            <Select value={f.heart_disease} onChange={(e) => set("heart_disease", +e.target.value)}>
              <option value={0}>No</option><option value={1}>Yes</option>
            </Select></div>
        </div>
        <div className="mt-5"><RunButton loading={loading} onClick={run}>Predict risk</RunButton></div>
        {err && <div className="mt-4"><ErrorNote msg={err} /><DevHint /></div>}
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold">Result</h2>
        {!res && !loading && <p className="text-sm text-slate-400">Enter patient details and run a prediction.</p>}
        {res && (
          <div className="space-y-5">
            <Verdict flag={res.flag} label={res.label} />
            <ProbabilityBar value={res.probability} threshold={res.threshold} danger={res.flag} />
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">
                What the model weighs most (global importance)
              </h3>
              <Bars items={res.global_importance.slice(0, 10).map((g) => ({ label: prettyFeature(g.feature), value: g.importance }))} />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
