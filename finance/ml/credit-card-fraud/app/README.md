# Credit-Card Fraud — ML & MLOps Dashboard

A client-facing showcase by **Khizar Sultan** demonstrating fraud detection under extreme
class imbalance (~0.17% fraud), with per-transaction explainability and live MLOps
monitoring: **predict → evaluate → explain → operate → monitor**.

The model is a cost-sensitive `HistGradientBoostingClassifier` (`class_weight='balanced'`)
— the production-recommended choice from `02_modeling` (strong recall, **no synthetic data**).

## What stakeholders see

| Tab | Question it answers | Techniques |
|-----|--------------------|------------|
| 🔎 **Predict & Explain** | *Why was this transaction flagged?* | Draw a real test transaction + **local SHAP** |
| 📊 **Performance** | *Can we trust it?* | PR-AUC, ROC-AUC, precision/recall, confusion matrix, threshold slider |
| 🧠 **Explainability** | *What drives it overall?* | **Global SHAP** feature importance |
| ⚙️ **System & Ops** | *Will it hold up in production?* | Latency p50/p95/p99, throughput, memory, CPU |
| 🌊 **Data Drift** | *Is live data still like training?* | **PSI** with a shift simulator |

> Because features `V1..V28` are PCA-anonymized, the Predict tab **draws a real
> transaction** (random fraud / random genuine / highest-risk) instead of manual entry.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py            # http://localhost:8501
```

## Docker
```bash
docker build -t fraud-dashboard . && docker run -p 7860:7860 fraud-dashboard
```

## Retrain the bundled artifact
`artifact.joblib` (model + preprocessor + tuned threshold + a test sample + SHAP
background) is produced by:
```bash
python train.py        # reads ../../data/finance-credit-card-fraud/creditcard.csv
```
The dashboard needs **only** `artifact.joblib` at runtime — the 150 MB raw CSV is not shipped.

## Files
- `app.py` — Streamlit dashboard (presentation only)
- `core.py` — model loading, metrics, SHAP, benchmarking, PSI drift (UI-agnostic)
- `features.py` — feature engineering + preprocessor (shared by training & inference)
- `train.py` — builds `artifact.joblib`
- `Dockerfile`, `requirements.txt`, `.streamlit/config.toml` — deployment
