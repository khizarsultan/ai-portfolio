# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. Scoped to **Credit Card Fraud Detection**.

**This project is structurally identical to `cybersecurity/ml/malicious-url-detection/`** — same
`app/` (Streamlit, multi-page via `st.navigation` + `views/` + `core.py` + `features.py` +
`train.py` + Docker), same `mlops/` (champion/challenger pipeline CLI over an MLflow registry with
a manual promotion gate), same `notebooks/` + `precompute_demo.py` bridge to the site. Read that
project's `CLAUDE.md` for the full shape and the artifact-vs-site-model distinction; this file only
lists the deltas.

## What it is

A **binary** fraud classifier on the canonical Kaggle credit-card benchmark: 284,807 transactions,
0.17% fraud (severe imbalance). Features are `Time`, `Amount`, and PCA components `V1`–`V28`. The
point of the project is honest handling of extreme imbalance: SMOTE / class-weighting and
evaluation on **precision-recall / AUPRC, not accuracy**.

## Deltas from the canonical (malicious-url) project

- **Task/target:** binary, `TARGET="Class"` (0 genuine / 1 fraud) — vs multi-class `type`.
- **Metrics (`mlops/config.py`):** `PRIMARY_METRIC="roc_auc"`, `GUARDRAIL_METRIC="pr_auc"` — vs
  macro-F1 / macro-recall for URLs. `REGISTERED_MODEL="fraud-risk"`, `EXPERIMENT="finance-fraud"`.
- **Drift columns:** `DRIFT_COLS=["V14","V17","V12","log_amount"]` (the most fraud-predictive PCA
  components + a log-amount feature) — vs URL-shape columns.
- **Imbalance handling** is the core modeling concern here (SMOTE via `imbalanced-learn` /
  class weights); the URL project instead cares about per-class recall balance.
- **Data:** `data/finance-credit-card-fraud/creditcard.csv` (~150 MB), gitignored.
- **Site bridge:** `precompute_demo.py` → `site/public/demo-data/fraud.json`; live user-input demo
  uses the slimmed `site/api/models/fraud.joblib` + `site/api/fraud.py`.

## Commands

```bash
cd app  && pip install -r requirements.txt && python train.py && streamlit run app.py   # :8501
cd mlops && python pipeline.py bootstrap                     # then run / evaluate / promote / status
```

Everything else — the two-artifact split (`app/artifact.joblib` full bundle vs the slimmed site
model), "computation in `core.py`, presentation in `views/`", leakage-safe featurization shared
between train and serve, and the gitignore list — matches the malicious-url project.
