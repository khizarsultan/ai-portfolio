// Shape of site/public/demo-data/fraud.json (produced offline by
// finance/ml/credit-card-fraud/precompute_demo.py). Binary, highly imbalanced.
export type SweepRow = { t: number; tp: number; fp: number; fn: number; tn: number; precision: number; recall: number; f1: number; accuracy: number };
export type Example = {
  name: string; amount: number; hour: number; actual: number;
  probability: number; flag: boolean; local: { feature: string; shap: number }[];
};
export type FraudData = {
  model_name: string; trained_on: string; threshold_default: number; prod_version: number | null;
  scores: Record<string, number>; confusion: number[][]; baseline: number; n_test: number;
  roc: [number, number][]; pr: [number, number][]; sweep: SweepRow[];
  latency: { p50: number; p95: number; p99: number; mean: number; throughput_rps: number; hist: { edges: number[]; counts: number[] } };
  resources: { process_mem_mb: number; system_mem_pct: number; cpu_pct: number; n_cores: number };
  global_importance: { feature: string; importance: number }[];
  examples: Example[];
  drift: { feature: string; PSI: number; status: string }[];
  mlops: {
    registry: { version: number; alias: string; roc_auc: number; pr_auc: number; model_name: string }[];
    prod_version: number | null;
    champion: { version: number | null; roc_auc: number; pr_auc: number; recall: number; precision: number };
    challenger: { version: number; roc_auc: number; pr_auc: number; recall: number; precision: number };
    illustrative: boolean; gate_passed: boolean; gate_reasons: string[];
    drift_monitor: { feature: string; PSI: number; status: string }[];
  };
};

// Live API (/api/fraud) response.
export type FraudStep = { stage: string; detail: Record<string, unknown> };
export type FraudLive = {
  probability: number; threshold: number; flag: boolean; label: string;
  amount: number; hour: number; steps: FraudStep[]; model_name: string;
};

export function nearestSweep(sweep: SweepRow[], t: number): SweepRow {
  return sweep.reduce((a, b) => (Math.abs(b.t - t) < Math.abs(a.t - t) ? b : a));
}
