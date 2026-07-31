// Shape of site/public/demo-data/malicious-url.json (precompute_demo.py, multiclass).
export type UrlData = {
  model_name: string; classes: string[]; n_test: number;
  metrics: { accuracy: number; macro_f1: number; macro_recall: number; macro_roc_auc: number };
  per_class: { cls: string; precision: number; recall: number; f1: number; support: number }[];
  confusion_norm: number[][]; confusion_counts: number[][];
  global_importance: { feature: string; importance: number }[];
  examples: { name: string; url: string; predicted: string; proba: Record<string, number>; local: { feature: string; shap: number }[] }[];
  latency: { p50: number; p95: number; p99: number; mean: number; throughput_rps: number; hist: { edges: number[]; counts: number[] } };
  resources: { process_mem_mb: number; system_mem_pct: number; cpu_pct: number; n_cores: number };
  drift: { feature: string; PSI: number; status: string }[];
  prod_version: number | null;
  mlops: {
    registry: { version: number; alias: string; roc_auc: number; pr_auc: number; model_name: string }[];
    prod_version: number | null;
    champion: { version: number | null; macro_f1: number; macro_recall: number; macro_roc_auc: number; accuracy: number };
    challenger: { version: number; macro_f1: number; macro_recall: number; macro_roc_auc: number; accuracy: number };
    illustrative: boolean; gate_passed: boolean; gate_reasons: string[];
    drift_monitor: { feature: string; PSI: number; status: string }[];
  };
};

// Live API (/api/malicious-url) response.
export type UrlStage = { key: string; title: string; summary: string; kind: string; data: unknown };
export type UrlLive = {
  url: string; predicted_class: string; malicious: boolean;
  probabilities: Record<string, number>; flags: { key: string; label: string; on: boolean }[];
  model_name: string; stages: UrlStage[];
};

export const CLASS_COLORS: Record<string, string> = {
  benign: "#16a34a", defacement: "#d97706", malware: "#dc2626", phishing: "#ea6a34",
};
export const classColor = (c: string) => CLASS_COLORS[c] ?? "#2a78d6";
