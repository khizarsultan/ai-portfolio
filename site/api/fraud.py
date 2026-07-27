"""Vercel Python function — Credit-card fraud detection.

GET  /api/fraud  -> preset example transactions (real rows) + global importance
POST /api/fraud  -> {raw: {Time, V1..V28, Amount}} -> fraud probability

The 28 V-features are anonymized PCA components (not human-readable), so the UI drives
this from preset real transactions; a user may still override Amount and re-score.
"""
from http.server import BaseHTTPRequestHandler
import json, os
import numpy as np
import pandas as pd
import joblib

_ART = joblib.load(os.path.join(os.path.dirname(__file__), "models", "fraud.joblib"))

AMOUNT_BINS = [-0.01, 1, 10, 50, 200, 1e9]
AMOUNT_LABELS = ["<1", "1-10", "10-50", "50-200", "200+"]


def _add_features(df):
    d = df.copy()
    d["hour"] = (d["Time"] // 3600 % 24).astype(int)
    d["log_amount"] = np.log1p(d["Amount"])
    d["amount_zero"] = (d["Amount"] == 0).astype(int)
    d["amount_bin"] = pd.cut(d["Amount"], bins=AMOUNT_BINS, labels=AMOUNT_LABELS)
    return d


def predict(raw):
    raw = {k: (float(v) if k != "Time" else float(v)) for k, v in raw.items()}
    df = _add_features(pd.DataFrame([raw]))
    Xt = _ART["preprocessor"].transform(df[list(_ART["input_cols"])])
    p = float(_ART["model"].predict_proba(Xt)[:, 1][0])
    thr = _ART["threshold"]
    return {
        "probability": round(p, 4),
        "threshold": round(thr, 4),
        "flag": bool(p >= thr),
        "label": "Fraudulent" if p >= thr else "Legitimate",
        "amount": round(float(raw["Amount"]), 2),
        "hour": int(df["hour"].iloc[0]),
        "global_importance": _ART["global_importance"],
        "model_name": _ART["model_name"],
    }


def _meta():
    return {
        "model_name": _ART["model_name"],
        "threshold": round(_ART["threshold"], 4),
        "examples": _ART["examples"],
        "global_importance": _ART["global_importance"],
    }


class handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        self._json(200, _meta())

    def do_POST(self):
        try:
            n = int(self.headers.get("content-length", 0) or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            raw = body.get("raw", body)
            self._json(200, predict(raw))
        except Exception as e:
            self._json(400, {"error": str(e)})
