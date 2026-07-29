"""Config for the URL-threat MLOps pipeline."""
from __future__ import annotations
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _p(*parts):
    return os.path.abspath(os.path.join(HERE, *parts))


RAW_CSV = _p("..", "..", "data", "cybersecurity-malicious-urls", "malicious_phish.csv")
TARGET = "type"
RANDOM_STATE = 42
SAMPLE_ROWS = 120000                 # subsample for fast featurization in the demo

TRACKING_URI = f"sqlite:///{_p('mlflow.db')}"
ARTIFACT_ROOT = _p("mlartifacts")
EXPERIMENT = "cybersecurity-url"
REGISTERED_MODEL = "url-threat"
ALIAS_PROD = "production"
ALIAS_CHALLENGER = "challenger"

FEATURE_STORE = _p("feature_store")
REPORTS_DIR = _p("reports")
STATE_DIR = _p("state")
SERVING_ARTIFACT = _p("..", "app", "artifact.joblib")

DRIFT_SHARE_THRESHOLD = 0.4
DRIFT_COLS = ["url_len", "n_digits", "digit_ratio", "url_entropy"]

PRIMARY_METRIC = "macro_f1"
GUARDRAIL_METRIC = "macro_recall"
MIN_IMPROVEMENT = 0.0
GUARDRAIL_TOLERANCE = 0.02

TEST_SAMPLE = 12000
REF_SAMPLE = 12000

for d in (ARTIFACT_ROOT, FEATURE_STORE, REPORTS_DIR, STATE_DIR):
    os.makedirs(d, exist_ok=True)
