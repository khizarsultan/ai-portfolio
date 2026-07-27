"""Central configuration for the healthcare MLOps pipeline.

One place for every path, threshold, and policy knob so the CLI, the steps, and the
crontab all agree. Paths are resolved relative to this file so the pipeline runs from
any working directory.
"""
from __future__ import annotations
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _p(*parts):
    return os.path.abspath(os.path.join(HERE, *parts))


# ------------------------------ data ------------------------------
RAW_CSV = _p("..", "app", "diabetes_prediction_dataset.csv")   # source of record
TARGET = "diabetes"
RANDOM_STATE = 42

# ------------------------------ MLflow ----------------------------
# Registry needs a DB-backed store; sqlite keeps it self-contained & local.
TRACKING_URI = f"sqlite:///{_p('mlflow.db')}"
ARTIFACT_ROOT = _p("mlartifacts")
EXPERIMENT = "healthcare-diabetes"
REGISTERED_MODEL = "diabetes-risk"
ALIAS_PROD = "production"          # champion currently serving
ALIAS_CHALLENGER = "challenger"   # candidate under evaluation

# ------------------------------ stores ----------------------------
FEATURE_STORE = _p("feature_store")      # versioned engineered-feature snapshots
REPORTS_DIR = _p("reports")              # drift + evaluation reports (html/json)
STATE_DIR = _p("state")                  # pending-approval records, run ledger
SERVING_ARTIFACT = _p("..", "app", "diabetes_model.joblib")   # what the dashboard loads

# ------------------------------ policy ----------------------------
# Drift: dataset is "drifted" when the share of drifted columns exceeds this.
DRIFT_SHARE_THRESHOLD = 0.4
DRIFT_COLS = ["age", "bmi", "HbA1c_level", "blood_glucose_level"]

# Promotion gate: a challenger may be promoted only if it beats the champion on the
# primary metric by at least MIN_IMPROVEMENT (or if there is no champion yet).
PRIMARY_METRIC = "roc_auc"          # ranking metric, threshold-independent
GUARDRAIL_METRIC = "pr_auc"         # must not regress by more than GUARDRAIL_TOLERANCE
MIN_IMPROVEMENT = 0.0               # challenger must be >= champion on PRIMARY_METRIC
GUARDRAIL_TOLERANCE = 0.02          # allow tiny noise on the guardrail metric

for d in (ARTIFACT_ROOT, FEATURE_STORE, REPORTS_DIR, STATE_DIR):
    os.makedirs(d, exist_ok=True)
