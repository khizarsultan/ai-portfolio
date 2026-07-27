"""Vercel Python function — SMS spam / malicious message detection.

GET  /api/sms-spam  -> model metadata + example messages
POST /api/sms-spam  -> {text} -> spam probability + per-token contributions (true local
                        explanation, since the model is linear: tfidf(token) * coef(token)).
"""
from http.server import BaseHTTPRequestHandler
import json, os
import numpy as np
import joblib

_ART = joblib.load(os.path.join(os.path.dirname(__file__), "models", "sms.joblib"))

EXAMPLES = [
    {"label": "Prize scam", "text": "Congratulations! You've WON a FREE $1000 gift card. Click http://bit.ly/claim now to claim."},
    {"label": "Bank phish", "text": "URGENT: your account is locked. Verify at http://secure-bank-login.com to restore access."},
    {"label": "Normal message", "text": "Hey, are we still meeting for lunch at 1pm today?"},
]


def predict(text):
    v = _ART["vectorizer"].transform([text])
    p = float(_ART["model"].predict_proba(v)[:, 1][0])
    contrib = v.multiply(_ART["coef"]).toarray().ravel()
    idx = np.nonzero(contrib)[0]
    order = sorted(idx, key=lambda i: -abs(contrib[i]))[:10]
    tokens = [{"token": str(_ART["vocab"][i]), "contribution": round(float(contrib[i]), 4)} for i in order]
    thr = _ART["threshold"]
    return {
        "probability": round(p, 4),
        "threshold": round(thr, 4),
        "flag": bool(p >= thr),
        "label": "Spam / malicious" if p >= thr else "Benign (ham)",
        "tokens": tokens,
        "model_name": _ART["model_name"],
    }


def _meta():
    return {"model_name": _ART["model_name"], "threshold": round(_ART["threshold"], 4), "examples": EXAMPLES}


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
            text = (body.get("text") or "").strip()
            if not text:
                return self._json(400, {"error": "empty text"})
            self._json(200, predict(text))
        except Exception as e:
            self._json(400, {"error": str(e)})
