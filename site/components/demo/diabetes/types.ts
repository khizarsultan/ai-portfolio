// Shape of site/public/demo-data/diabetes.json (produced offline by
// healthcare/ml/diabetes-prediction/precompute_demo.py).
export type SweepRow = { t: number; tp: number; fp: number; fn: number; tn: number; precision: number; recall: number; f1: number; accuracy: number };
export type Patient = {
  name: string; input: Record<string, string | number>; probability: number;
  local: { feature: string; shap: number }[];
  whatif: Record<string, { label: string; curve: [number, number][]; current: number; flip: number | null }>;
};
export type DemoData = {
  model_name: string; trained_on: string; threshold_default: number; prod_version: number | null;
  scores: Record<string, number>; confusion: number[][]; baseline: number; n_test: number;
  roc: [number, number][]; pr: [number, number][]; sweep: SweepRow[];
  latency: { p50: number; p95: number; p99: number; mean: number; throughput_rps: number; hist: { edges: number[]; counts: number[] } };
  resources: { process_mem_mb: number; system_mem_pct: number; cpu_pct: number; n_cores: number };
  global_importance: { feature: string; importance: number }[];
  patients: Patient[];
  drift: { feature: string; PSI: number; status: string }[];
  mlops: {
    registry: { version: number; alias: string; roc_auc: number; pr_auc: number; recall: number; precision: number }[];
    prod_version: number | null; gate_passed: boolean | null; gate_reasons: string[];
    champion_version: number | null; challenger_version: number | null;
    champion_metrics: Record<string, number>; challenger_metrics: Record<string, number>;
    approvals: { timestamp: string; challenger_version: number; previous_champion: number; approver: string; reason: string; action: string }[];
    drift_trigger: { drifted?: boolean; share_of_drifted_columns?: number; threshold?: number; columns?: { feature: string; PSI: number; status: string }[] };
  };
};

export function nearestSweep(sweep: SweepRow[], t: number): SweepRow {
  return sweep.reduce((a, b) => (Math.abs(b.t - t) < Math.abs(a.t - t) ? b : a));
}
