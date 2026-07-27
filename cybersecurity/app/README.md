# Malicious URL Detection — ML & MLOps Dashboard

A client-facing showcase by **Khizar Sultan**: a 4-class URL threat classifier
(benign / defacement / malware / phishing) with per-URL explainability and live MLOps
monitoring — **classify → evaluate → explain → operate → monitor**.

The model is a cost-sensitive `HistGradientBoostingClassifier` (`class_weight='balanced'`)
— the security-recommended choice from `02_modeling` (best recall on **malware** and
**phishing**, the classes it most matters to catch).

## What stakeholders see

| Tab | Question it answers | Techniques |
|-----|--------------------|------------|
| 🔎 **Classify & Explain** | *Is this URL dangerous, and why?* | Paste a URL → class probabilities + **local SHAP** |
| 📊 **Performance** | *Can we trust it?* | Macro-F1, per-class recall, confusion matrix |
| 🧠 **Explainability** | *What drives it overall?* | **Global SHAP** across all classes |
| ⚙️ **System & Ops** | *Will it hold up in production?* | Latency p50/p95/p99, throughput, memory, CPU |
| 🌊 **Data Drift** | *Is live traffic still like training?* | **PSI** with a shift simulator |

> Features are engineered live from the raw URL string (length, digits, host/path shape,
> entropy, TLD, IP-host & suspicious-keyword flags) — the same code path as training.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py            # http://localhost:8501
```

## Docker
```bash
docker build -t url-dashboard . && docker run -p 7860:7860 url-dashboard
```

## Retrain the bundled artifact
```bash
python train.py     # reads ../../data/cybersecurity-malicious-urls/malicious_phish.csv
```
The dashboard needs **only** `artifact.joblib` at runtime — the 85 MB raw CSV is not shipped.

## Files
- `app.py` — Streamlit dashboard (presentation only)
- `core.py` — multi-class metrics, SHAP, benchmarking, PSI drift (UI-agnostic)
- `features.py` — URL feature engineering + preprocessor (shared by training & live input)
- `train.py` — builds `artifact.joblib`
- `Dockerfile`, `requirements.txt`, `.streamlit/config.toml` — deployment
