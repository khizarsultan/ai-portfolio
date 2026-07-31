"""Vercel Python function — Diabetes risk prediction.

GET  /api/diabetes  -> model metadata + a default patient + global feature importance
POST /api/diabetes  -> {gender, age, hypertension, heart_disease, smoking_history,
                        bmi, HbA1c_level, blood_glucose_level} -> risk probability

Feature engineering is inlined (identical to the training-time preprocessing) so the
function is fully self-contained — no cross-module imports on the serverless runtime.
"""
from http.server import BaseHTTPRequestHandler
import json, os
import numpy as np
import pandas as pd
import joblib

_ART = joblib.load(os.path.join(os.path.dirname(__file__), "models", "diabetes.joblib"))

RAW_COLS = ["gender", "age", "hypertension", "heart_disease",
            "smoking_history", "bmi", "HbA1c_level", "blood_glucose_level"]

FIELDS = [
    {"name": "gender", "label": "Gender", "type": "select", "options": ["Female", "Male", "Other"]},
    {"name": "age", "label": "Age", "type": "number", "min": 1, "max": 100, "step": 1},
    {"name": "bmi", "label": "BMI", "type": "number", "min": 10, "max": 60, "step": 0.1},
    {"name": "HbA1c_level", "label": "HbA1c level (%)", "type": "number", "min": 3, "max": 15, "step": 0.1},
    {"name": "blood_glucose_level", "label": "Blood glucose (mg/dL)", "type": "number", "min": 50, "max": 350, "step": 1},
    {"name": "smoking_history", "label": "Smoking history", "type": "select",
     "options": ["never", "former", "current", "ever", "not current", "unknown"]},
    {"name": "hypertension", "label": "Hypertension", "type": "bool"},
    {"name": "heart_disease", "label": "Heart disease", "type": "bool"},
]


def _add_features(df):
    d = df.copy()
    d["hba1c_category"] = pd.cut(d["HbA1c_level"], bins=[-np.inf, 5.7, 6.4, np.inf],
                                 labels=["normal", "prediabetic", "high"])
    d["glucose_category"] = pd.cut(d["blood_glucose_level"], bins=[-np.inf, 140, 199, np.inf],
                                   labels=["normal", "prediabetic", "high"])
    d["age_group"] = pd.cut(d["age"], bins=[0, 12, 18, 35, 50, 65, np.inf],
                            labels=["child", "teen", "young_adult", "adult", "middle_age", "senior"])
    d["comorbidity_count"] = d["hypertension"] + d["heart_disease"]
    return d


def predict(inp):
    row = {c: inp[c] for c in RAW_COLS}
    for k in ("age", "bmi", "HbA1c_level", "blood_glucose_level"):
        row[k] = float(row[k])
    for k in ("hypertension", "heart_disease"):
        row[k] = int(row[k])
    df = pd.DataFrame([row]); df["bmi_missing"] = 0
    eng = _add_features(df)                     # real feature engineering
    engineered = {
        "hba1c_category": str(eng["hba1c_category"].iloc[0]),
        "glucose_category": str(eng["glucose_category"].iloc[0]),
        "age_group": str(eng["age_group"].iloc[0]),
        "comorbidity_count": int(eng["comorbidity_count"].iloc[0]),
    }
    Xt = _ART["preprocessor"].transform(eng)    # scale + one-hot encode
    n_features = int(Xt.shape[1])
    p = float(_ART["model"].predict_proba(Xt)[:, 1][0])
    thr = _ART["threshold"]
    # Under-the-hood trace: the actual stages this request ran through, with real
    # values — so a viewer can see this is a live model call, not a lookup.
    steps = [
        {"stage": "1 · Input received", "detail": {k: row[k] for k in RAW_COLS}},
        {"stage": "2 · Feature engineering", "detail": engineered},
        {"stage": "3 · Preprocessing / encoding",
         "detail": {"encoded_features": n_features, "ops": "impute → scale numeric → one-hot categoricals"}},
        {"stage": "4 · Model inference",
         "detail": {"model": _ART["model_name"], "raw_probability": round(p, 4)}},
        {"stage": "5 · Decision @ threshold",
         "detail": {"threshold": round(thr, 4), "rule": f"{round(p,4)} {'≥' if p >= thr else '<'} {round(thr,4)}",
                    "verdict": "High risk" if p >= thr else "Low risk"}},
    ]
    return {
        "probability": round(p, 4),
        "threshold": round(thr, 4),
        "flag": bool(p >= thr),
        "label": "High diabetes risk" if p >= thr else "Low diabetes risk",
        "steps": steps,
        "global_importance": _ART["global_importance"],
        "model_name": _ART["model_name"],
    }


def _meta():
    return {
        "model_name": _ART["model_name"],
        "threshold": round(_ART["threshold"], 4),
        "fields": FIELDS,
        "default_inp": _ART["default_inp"],
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
            self._json(200, predict(body))
        except Exception as e:
            self._json(400, {"error": str(e)})
