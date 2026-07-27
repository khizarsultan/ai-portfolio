# Diabetes Risk — ML & MLOps Dashboard

A client-facing showcase by **Khizar Sultan** demonstrating an end-to-end ML +
MLOps workflow on a single model: **predict → explain → evaluate → operate →
monitor**, all in one Streamlit app.

The model is a `HistGradientBoostingClassifier` trained on 100k patient records
to predict diabetes risk, with a decision threshold tuned on a held-out split.

## What stakeholders see

| Tab | Question it answers | Techniques |
|-----|--------------------|------------|
| 🔮 **Predict & Explain** | *Why did the model flag this patient?* | Live inference + **local SHAP** |
| 📊 **Performance** | *Can we trust it?* | ROC/PR-AUC, precision/recall, confusion matrix, threshold control |
| 🧠 **Explainability** | *What drives it overall?* | **Global SHAP** feature importance |
| ⚙️ **System & Ops** | *Will it hold up in production?* | Latency p50/p95/p99, throughput, memory, CPU |
| 🌊 **Data Drift** | *Is the live data still like training?* | **PSI** with a shift simulator |

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
# open http://localhost:8501
```

## Run with Docker

```bash
docker build -t diabetes-dashboard .
docker run -p 7860:7860 diabetes-dashboard
# open http://localhost:7860
```

## Deploy to Hugging Face Spaces (free CPU)

1. Create a new Space → **SDK: Docker**.
2. Push the contents of this `app/` folder to the Space repo:
   ```bash
   git init && git remote add origin https://huggingface.co/spaces/<user>/<space>
   git add . && git commit -m "Diabetes MLOps dashboard"
   git push origin main
   ```
3. The Space builds the `Dockerfile` and serves on port 7860 automatically.

> The `diabetes_model.joblib` artifact and `diabetes_prediction_dataset.csv`
> ship with the app so the demo is fully self-contained (no external data pull).

## Files

- `app.py` — Streamlit dashboard (presentation only).
- `core.py` — model loading, metrics, SHAP, benchmarking, PSI drift (UI-agnostic, testable).
- `preprocessing.py` — leakage-safe cleaning / feature engineering / transforms (shared with training).
- `Dockerfile`, `requirements.txt`, `.streamlit/config.toml` — deployment.
