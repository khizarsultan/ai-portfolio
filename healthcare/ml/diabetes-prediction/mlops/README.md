# Healthcare — MLOps Pipeline

A complete, self-contained MLOps lifecycle for the diabetes-risk model, built by
**Khizar Sultan** on industry-standard OSS (**MLflow** + **Evidently**). It implements the
four planes of a production ML system:

```
 authoring            registry / evidence            gate                 operations
 ─────────            ──────────────────             ────                 ──────────
 train challenger ─▶  MLflow versions + tags   ─▶  auto-eval vs champion ─▶ serving artifact
 (reference+window)   aliases: production /        + guardrails         ─▶  dashboard loads it
        ▲             challenger, lineage          + MANUAL approval          │
        │                                                                     ▼
        └──────────────── drift signal (Evidently + PSI) ◀────────── monitor production data
```

Everything runs locally — no cloud. The retraining **trigger** is deterministic PSI;
**Evidently** renders the governance-grade HTML drift report alongside it.

## The lifecycle (each stage is a CLI command)

| Command | What it does |
|---|---|
| `bootstrap` | Train the first champion on the reference split, register as `production`, roll out to serving |
| `make-window [--n --drift]` | Draw a new "production" data window into the **feature store** (versioned snapshot) |
| `check-drift` | PSI per feature + Evidently HTML report: latest window vs training reference |
| `retrain` | Train a **challenger** on reference + latest window; log run + register version + lineage |
| `evaluate` | Score challenger **vs champion** on the frozen holdout; apply the promotion gate |
| `promote --approve --by <you>` | **Human sign-off** → move `production` alias, audit-trail the version, roll out to serving |
| `status` | Registry versions, aliases, pending approval, serving artifact |
| `run [--drift]` | Drift-triggered flow: window → drift → *(if drifted)* retrain → evaluate → stop for approval |

## Quick start
```bash
pip install -r requirements.txt
python pipeline.py bootstrap                    # establish champion v1
python pipeline.py run --drift                  # simulate drift → retrain → evaluate
python pipeline.py status                        # see the pending challenger
python pipeline.py promote --approve --by you --reason "beats champion, guardrail ok"
mlflow ui --backend-store-uri sqlite:///mlflow.db   # http://localhost:5000
```

## How the pieces map to best practices
- **Model registry as source of truth** — every version links to its run, metrics, dataset
  version, and threshold (MLflow tags). Champion/challenger via **aliases** (`production`,
  `challenger`) — the modern replacement for deprecated stages.
- **Drift-triggered retraining** — `run` retrains **only** when the drifted-column share
  exceeds `DRIFT_SHARE_THRESHOLD` (config). Schedule it with `crontab.example`.
- **Champion vs challenger gate** — a challenger must beat the champion on the primary
  metric (`roc_auc`) and not regress the guardrail (`pr_auc`) beyond tolerance.
- **Manual approval + audit trail** — promotion is never automatic; every decision is
  appended to `state/approvals.jsonl` and stamped on the model version
  (`approved_by`, `approved_at`, `approval_reason`).
- **Serving integration** — the approved model is exported to the exact artifact the
  Streamlit dashboard loads (`../app/diabetes_model.joblib`), so **approval = go-live**.
- **Feature store** — engineered snapshots are versioned under `feature_store/` with a
  metadata sidecar (hash, row count, drift flag) and linked to each training run.

## Configuration
All thresholds and paths live in `config.py`: drift threshold & columns, primary/guardrail
metrics, min-improvement, MLflow URIs, and the serving path.

## Layout
```
mlops/
  pipeline.py           # CLI (the orchestrator)
  config.py             # all thresholds & paths
  preprocessing.py      # shared feature engineering (from the training notebooks)
  steps/
    ingest.py           # data roles + feature store
    modeling.py         # train + evaluate (pure sklearn)
    drift.py            # PSI trigger + Evidently report
    registry.py         # MLflow tracking + registry (aliases, tags, lineage)
    evaluate.py         # champion/challenger gate
    promote.py          # manual approval + serving rollout
  crontab.example       # scheduled drift-triggered retraining
  requirements.txt
  # generated at runtime: mlflow.db, mlartifacts/, feature_store/, reports/, state/
```

> Sources for the design: MLflow ML-lifecycle & model-registry docs, Evidently drift
> monitoring, and current champion/challenger + approval-gate MLOps practice (2025).
