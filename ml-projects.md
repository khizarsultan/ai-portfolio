# ML Projects — Selected Open-Source Datasets

Three Machine Learning projects (one per domain) chosen for the portfolio. All datasets are public, CSV-based, and light enough to train and demo on free-tier CPU (Hugging Face Spaces).

---

## 1. Healthcare — Diabetes Prediction

**Goal:** Binary classification — predict whether a patient has diabetes from medical & demographic data.

- **Dataset:** Diabetes Prediction Dataset
- **Source:** https://www.kaggle.com/datasets/iammustafatz/diabetes-prediction-dataset
- **Size:** ~100,000 rows
- **Format:** CSV (single file)
- **Features:** `gender`, `age`, `hypertension`, `heart_disease`, `smoking_history`, `bmi`, `HbA1c_level`, `blood_glucose_level`
- **Target:** `diabetes` (0 = no, 1 = yes)
- **License:** Open / public (Kaggle) — verify CC0 on page
- **Why:** Clean, tabular, mild class imbalance — good for logistic regression / XGBoost + SHAP explainability.

---

## 2. Cybersecurity — Malicious URL Detection

**Goal:** Multi-class classification — flag URLs as benign or malicious (phishing / malware / defacement).

- **Dataset:** Malicious URLs Dataset
- **Source:** https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset
- **Size:** ~651,000 URLs
- **Format:** CSV (single file)
- **Columns:** `url` (raw string), `type` (label)
- **Classes:** `benign`, `defacement`, `phishing`, `malware`
- **License:** Open / public (Kaggle) — verify on page
- **Why:** Requires lexical feature engineering from raw URLs (length, digits, symbols, subdomains, etc.) — strong showcase of the full ML pipeline; runs on CPU.

> Alternative if this dataset is unavailable: "Malicious URL Detection Dataset (Enhanced 2026)" — https://www.kaggle.com/datasets/moutasmtamimi/malicious-url-detection-dataset-enhanced-2026

---

## 3. Finance — Credit Card Fraud Detection

**Goal:** Binary classification on highly imbalanced data — detect fraudulent transactions.

- **Dataset:** Credit Card Fraud Detection
- **Source:** https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
- **Size:** 284,807 transactions; 492 fraud (~0.172% — severe imbalance)
- **Format:** CSV (single file, ~150 MB)
- **Features:** `Time`, `Amount`, `V1`–`V28` (PCA-anonymized components)
- **Target:** `Class` (0 = genuine, 1 = fraud)
- **License:** Open Database License (ODbL) — verify on page
- **Why:** Canonical benchmark; demonstrates handling class imbalance (SMOTE / class weights) and precision-recall / AUPRC evaluation.

---

## Common stack (planned)
- **Training:** Python, pandas, scikit-learn, XGBoost (+ SHAP for explainability)
- **Demo:** Gradio app deployed as a Hugging Face Space (free, CPU)
- **Code:** Public GitHub repo per project — notebook (EDA → train → eval) + README case study
- **Data note:** Datasets pulled via `kagglehub` (no auth needed); large files not committed to repos (size/license).

## Downloaded & verified (local)

| Project | File | Local path | Verified shape |
|---|---|---|---|
| Diabetes | `diabetes_prediction_dataset.csv` | `data/healthcare-diabetes/` | 100,000 × 9 — target `diabetes`: 91,500 neg / 8,500 pos |
| Malicious URLs | `malicious_phish.csv` | `data/cybersecurity-malicious-urls/` | 651,191 × 2 — `type`: benign 428,103 / defacement 96,457 / phishing 94,111 / malware 32,520 |
| Credit Card Fraud | `creditcard.csv` | `data/finance-credit-card-fraud/` | 284,807 × 31 — `Class`: 284,315 genuine / 492 fraud (0.173%) |

Download command used: `kagglehub.dataset_download("<slug>")`

## Open items to confirm before building
- Exact license on each Kaggle page (needed before redistributing / committing data).
