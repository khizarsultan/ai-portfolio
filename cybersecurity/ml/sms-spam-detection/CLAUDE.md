# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. Scoped to **SMS Spam Detection**. See the repo-root `CLAUDE.md` for monorepo-wide
conventions.

## What it is

The **minimal ML project** in the portfolio: a TF-IDF + Logistic Regression classifier that flags
SMS as `spam (malicious)` vs `ham (benign)`. Unlike the other two ML projects, it has **no `mlops/`
pipeline and no `notebooks/`** — just `app/` plus a `precompute_demo.py`.

Its distinguishing feature is **exact, per-token explainability**: because the model is linear, a
prediction's word contributions are `tfidf(token) × coefficient` — a true explanation, not a
post-hoc approximation. Preserve this property; don't swap in a non-linear model without replacing
the explanation logic (`core.explain_text`).

## Structure

- `app/app.py` — a **single-file, tabbed** Streamlit app (Classify & Explain / Performance /
  Explainability / System & Ops / Data Drift). Note this differs from the malicious-url and fraud
  apps, which are multi-page via `st.navigation` + a `views/` folder.
- `app/core.py` — UI-agnostic logic: `load_artifact`, `proba_text`, `explain_text` (per-token
  contributions), `global_tokens`, metrics, latency benchmark, PSI drift.
- `app/train.py` — builds `artifact.joblib`. The bundle carries `vectorizer`, `model`, `threshold`
  (F1-optimal, tuned on the validation split), `vocab`, `coef`, and held-out test/ref text.
- `app/ui.py`, `app/.streamlit/config.toml` — shared branding/theme.
- `precompute_demo.py` (project root) → writes `site/public/demo-data/` for the site; the live
  user-input demo is `site/api/sms-spam.py` + the slimmed `site/api/models/sms-spam.joblib`.

## Commands

```bash
cd app
pip install streamlit plotly scikit-learn pandas numpy    # (no requirements.txt in this project)
python train.py            # rebuild artifact.joblib — reads ../../../data/cybersecurity-sms-spam/sms_spam.csv
streamlit run app.py       # http://localhost:8501
```

## Gotchas

- Training data path has **three** `../` (`../../../data/...`), one deeper than the other ML
  projects because there's no `mlops/` layer — mind this if copying paths across projects.
- `artifact.joblib`, `*.csv`, `data/` are gitignored/regenerable. The vectorizer must be pickled
  and unpickled against the sklearn version pinned in `site/requirements.txt` for the site demo.
