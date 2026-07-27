"""Config for the fraud MLOps pipeline (paths, thresholds, policy)."""
from __future__ import annotations
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _p(*parts):
    return os.path.abspath(os.path.join(HERE, *parts))


RAW_CSV = _p("..", "..", "data", "finance-credit-card-fraud", "creditcard.csv")
TARGET = "Class"
RANDOM_STATE = 42

TRACKING_URI = f"sqlite:///{_p('mlflow.db')}"
ARTIFACT_ROOT = _p("mlartifacts")
EXPERIMENT = "finance-fraud"
REGISTERED_MODEL = "fraud-risk"
ALIAS_PROD = "production"
ALIAS_CHALLENGER = "challenger"

FEATURE_STORE = _p("feature_store")
REPORTS_DIR = _p("reports")
STATE_DIR = _p("state")
SERVING_ARTIFACT = _p("..", "app", "artifact.joblib")   # full dashboard bundle

DRIFT_SHARE_THRESHOLD = 0.4
DRIFT_COLS = ["V14", "V17", "V12", "log_amount"]

PRIMARY_METRIC = "roc_auc"
GUARDRAIL_METRIC = "pr_auc"
MIN_IMPROVEMENT = 0.0
GUARDRAIL_TOLERANCE = 0.02

TEST_SAMPLE = 15000
REF_SAMPLE = 15000

for d in (ARTIFACT_ROOT, FEATURE_STORE, REPORTS_DIR, STATE_DIR):
    os.makedirs(d, exist_ok=True)
