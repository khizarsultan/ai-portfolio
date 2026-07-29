"""Vercel Python function — Malicious URL detection (4-class).

GET  /api/malicious-url  -> classes, example URLs per class, global importance
POST /api/malicious-url  -> {url} -> predicted class + per-class probabilities + lexical flags

Lexical feature engineering is inlined (identical to training) so the function is
self-contained. Classes: benign / defacement / malware / phishing.
"""
from http.server import BaseHTTPRequestHandler
import json, os, re
import numpy as np
import pandas as pd
import joblib
from collections import Counter
from urllib.parse import urlparse

_ART = joblib.load(os.path.join(os.path.dirname(__file__), "models", "url.joblib"))

SHORTENERS = {"bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rebrand.ly"}
SUSPICIOUS = r"login|secure|account|update|bank|verify|signin|confirm|password|free|webscr|paypal|ebayisapi"
FLAG_LABELS = {"has_https": "Uses HTTPS", "has_at": "Contains '@'", "has_ip": "Raw IP host",
               "is_shortened": "URL shortener", "has_suspicious": "Suspicious keyword"}


def _host(u):
    t = u if u.lower().startswith("http") else "http://" + u
    try:
        return urlparse(t).netloc.split(":")[0]
    except ValueError:
        return t.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0].split(":")[0]


def _path(u):
    t = u if u.lower().startswith("http") else "http://" + u
    try:
        return urlparse(t).path or ""
    except ValueError:
        r = t.split("://", 1)[-1]
        return "/" + r.split("/", 1)[1] if "/" in r else ""


def _entropy(s):
    if not s:
        return 0.0
    n = len(s); c = Counter(s)
    return float(-sum((v / n) * np.log2(v / n) for v in c.values()))


def _featurize(url):
    s = pd.Series([url]).str.strip(); low = s.str.lower(); F = pd.DataFrame(index=s.index)
    F["url_len"] = s.str.len(); F["n_dots"] = s.str.count(r"\."); F["n_hyphen"] = s.str.count("-")
    F["n_digits"] = s.str.count(r"\d"); F["n_slash"] = s.str.count("/"); F["n_special"] = s.str.count(r"[@?%=&_~+]")
    host = s.map(_host); F["host_len"] = host.str.len(); F["path_len"] = s.map(_path).str.len()
    F["n_subdomains"] = host.str.count(r"\."); F["digit_ratio"] = (F["n_digits"] / F["url_len"]).fillna(0)
    F["url_entropy"] = s.map(_entropy); F["has_https"] = low.str.startswith("https").astype(int)
    F["has_at"] = s.str.contains("@").astype(int)
    F["has_ip"] = host.str.contains(r"^(?:\d{1,3}\.){3}\d{1,3}$", regex=True).astype(int)
    F["is_shortened"] = host.str.lower().isin(SHORTENERS).astype(int)
    F["has_suspicious"] = low.str.contains(SUSPICIOUS, regex=True).astype(int)
    F["scheme"] = np.where(low.str.startswith("https"), "https",
                           np.where(low.str.startswith("http"), "http", "none"))
    F["tld"] = host.str.rsplit(".", n=1).str[-1].str.lower().where(host.str.contains(r"\."), "none")
    F["tld"] = F["tld"].where(F["tld"].isin(set(_ART["top_tlds"])), "other")
    return F


# Engineered numeric features, grouped for a readable "under the hood" view.
_NUM_FEATURES = ["url_len", "host_len", "path_len", "n_dots", "n_hyphen", "n_digits",
                 "n_slash", "n_special", "n_subdomains", "digit_ratio", "url_entropy"]
_NUM_LABELS = {"url_len": "URL length", "host_len": "Host length", "path_len": "Path length",
               "n_dots": "Dots (.)", "n_hyphen": "Hyphens (-)", "n_digits": "Digits",
               "n_slash": "Slashes (/)", "n_special": "Special chars", "n_subdomains": "Subdomains",
               "digit_ratio": "Digit ratio", "url_entropy": "Char entropy"}


def _stages(url, F, Xt, proba, classes, pred, flags):
    """Real intermediate values at each step of the pipeline — the 'glass box' view."""
    f0 = F.iloc[0]
    host, path = _host(url), _path(url)
    dense = Xt.toarray()[0] if hasattr(Xt, "toarray") else np.asarray(Xt).ravel()
    num = [{"label": _NUM_LABELS[k],
            "value": round(float(f0[k]), 3) if k in ("digit_ratio", "url_entropy") else int(f0[k])}
           for k in _NUM_FEATURES]
    top = sorted(_ART["global_importance"], key=lambda d: -d["importance"])[:6]
    pmax = max(proba)
    return [
        {"key": "input", "title": "Raw input", "summary": "The URL as typed", "kind": "kv",
         "data": [{"label": "URL", "value": url}, {"label": "Host", "value": host or "—"},
                  {"label": "Path", "value": path or "/"}]},
        {"key": "features", "title": "Feature engineering",
         "summary": f"{len(_NUM_FEATURES)} lexical features from the raw string", "kind": "kv",
         "data": num},
        {"key": "flags", "title": "Lexical signals", "summary": "Binary red/green flags",
         "kind": "flags", "data": flags},
        {"key": "preprocess", "title": "Preprocessing",
         "summary": f"Scaled + one-hot encoded → {len(dense)}-dim vector", "kind": "vector",
         "data": {"dims": len(dense), "values": [round(float(x), 3) for x in dense[:16]],
                  "note": "Numeric features standardized; scheme + TLD one-hot encoded. First 16 dims shown."}},
        {"key": "model", "title": "Model", "summary": _ART["model_name"], "kind": "kv",
         "data": [{"label": "Algorithm", "value": _ART["model_name"]},
                  {"label": "Task", "value": "4-class classification"},
                  {"label": "Input dims", "value": len(dense)},
                  {"label": "Classes", "value": ", ".join(classes)}]},
        {"key": "prediction", "title": "Prediction",
         "summary": f"{pred} ({round(pmax * 100)}%)", "kind": "bars",
         "data": [{"label": c, "value": round(float(p), 4), "active": c == pred}
                  for c, p in zip(classes, proba)]},
        {"key": "explain", "title": "Why", "summary": "Top signals the model relies on",
         "kind": "importance",
         "data": [{"label": d["feature"], "value": round(float(d["importance"]), 4)} for d in top]},
    ]


def predict(url):
    F = _featurize(url)
    Xt = _ART["preprocessor"].transform(F[list(_ART["input_cols"])])
    proba = _ART["model"].predict_proba(Xt)[0]
    classes = [str(c) for c in _ART["model"].classes_]
    pred = classes[int(np.argmax(proba))]
    flags = [{"key": k, "label": FLAG_LABELS[k], "on": bool(int(F[k].iloc[0]))} for k in FLAG_LABELS]
    return {
        "url": url,
        "predicted_class": pred,
        "malicious": bool(pred != "benign"),
        "probabilities": {c: round(float(p), 4) for c, p in zip(classes, proba)},
        "flags": flags,
        "features": {"url_len": int(F["url_len"].iloc[0]), "host_len": int(F["host_len"].iloc[0]),
                     "n_subdomains": int(F["n_subdomains"].iloc[0]),
                     "url_entropy": round(float(F["url_entropy"].iloc[0]), 2)},
        "model_name": _ART["model_name"],
        "stages": _stages(url, F, Xt, proba, classes, pred, flags),
    }


def _meta():
    return {
        "model_name": _ART["model_name"],
        "classes": [str(c) for c in _ART["classes"]],
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
            url = (body.get("url") or "").strip()
            if not url:
                return self._json(400, {"error": "empty url"})
            self._json(200, predict(url))
        except Exception as e:
            self._json(400, {"error": str(e)})
