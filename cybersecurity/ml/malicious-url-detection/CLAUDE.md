# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. Scoped to **Malicious URL Detection**. See the repo-root `CLAUDE.md` for the
monorepo-wide two-track demo model and shared conventions. This project is the **canonical example
of the ML project shape** — the credit-card-fraud project is structurally identical (see its
`CLAUDE.md` for the deltas).

## What it is

A 4-class URL threat classifier (`benign / defacement / malware / phishing`) built from **lexical
features of the raw URL string** — it never fetches the URL. Deployed model is a cost-sensitive
`HistGradientBoostingClassifier(class_weight="balanced")`, chosen in `notebooks/02_modeling` for
best recall on malware & phishing (the classes that matter most to catch).

## The three sub-parts and how they connect

```
notebooks/   EDA + modeling — where the model choice is justified (01_eda, 02_modeling)
app/         Streamlit dashboard — trains + serves artifact.joblib (the full bundle)
mlops/       champion/challenger pipeline over an MLflow registry (drift-triggered retrain)
precompute_demo.py   offline: reads the app artifact + real registry -> site JSON
```

Two artifacts, do not confuse them:

- **`app/artifact.joblib`** — the *full* dashboard bundle: model + preprocessor **plus**
  `X_test/y_test/X_ref/background/examples`. Built by `app/train.py`. Also referenced by mlops as
  `SERVING_ARTIFACT`. Not committed (gitignored, regenerable), ~needs the 85 MB raw CSV to rebuild.
- **`site/api/models/malicious-url.joblib`** — the *slimmed* model (model + preprocessor only)
  that ships to Vercel for the live user-input demo. Different file, different repo location.

`precompute_demo.py` bridges this project → the site: it computes everything the site dashboards
render (metrics, SHAP numbers, drift, registry state) offline and writes
`site/public/demo-data/malicious-url.json`, so the Vercel site ships **numbers only** — no
shap/plotly/mlflow. The MLOps registry + drift in that JSON are real; the champion-vs-challenger
approval cycle is emitted as a clearly-flagged illustrative scenario (`illustrative=True`) because
no challenger/approval state is committed.

## Feature engineering is the shared contract

`app/features.py` engineers features from the raw URL (length, digit/entropy ratios, host/path
shape, TLD, IP-host & suspicious-keyword flags) and builds the sklearn preprocessor. The **same
code path runs at training time and on live input** — if you change featurization, you must
retrain the artifact (`python app/train.py`) or the preprocessor/model will mismatch. `mlops/` has
its own parallel `features.py`; keep them consistent. Top-TLDs are learned from the **training
split only** (leakage-safe) then mapped to all splits — preserve that.

## app/ — Streamlit dashboard (multi-page)

`app/app.py` wires pages via `st.navigation` (`views/executive_view.py`,
`views/model_view.py` [default], `views/mlops_view.py`); `ui.py` is shared branding/styling.
`core.py` holds all UI-agnostic logic (multi-class metrics, SHAP, latency benchmark, PSI drift) —
**put computation in `core.py`, presentation in `views/`.**

```bash
cd app
pip install -r requirements.txt
python train.py                 # rebuild artifact.joblib (needs the raw CSV under data/)
streamlit run app.py            # http://localhost:8501
docker build -t url-dashboard . && docker run -p 7860:7860 url-dashboard
```

## mlops/ — pipeline CLI

`mlops/pipeline.py` is a subcommand CLI over an MLflow registry (`mlflow.db`, sqlite) with
champion (`production`) / challenger aliases and a **manual promotion gate**. Steps live in
`mlops/steps/` (ingest, modeling, drift, evaluate, promote, registry, bundle). Policy is in
`mlops/config.py` — for this project: `TARGET="type"`, `PRIMARY_METRIC="macro_f1"`,
`GUARDRAIL_METRIC="macro_recall"`, `REGISTERED_MODEL="url-threat"`, drift over URL-shape columns.

```bash
cd mlops
python pipeline.py bootstrap                    # train champion on the reference split
python pipeline.py make-window --drift          # snapshot a (shifted) serving window
python pipeline.py run --drift                  # make-window -> check-drift -> retrain+evaluate
python pipeline.py evaluate                     # challenger vs champion, prints the gate reasons
python pipeline.py promote --approve --by you   # manual gate (--reject to decline)
python pipeline.py status
```

## Gotchas

- `data/`, `*.csv`, `*.joblib`, `mlflow.db`, `mlruns/`, `feature_store/` are gitignored — all
  regenerable. Datasets come from Kaggle via `kagglehub` (slug in root `ml-projects.md`).
- After changing the model/features, regenerate in order: `app/train.py` →
  `precompute_demo.py` → (and reslim the site model if the live demo model changed).
