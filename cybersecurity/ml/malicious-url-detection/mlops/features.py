"""Shared URL lexical feature engineering + preprocessor.

Used by train.py (batch) and the live dashboard (single URL) so training and inference
produce identical features. All features are row-wise functions of the URL string.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from collections import Counter
from urllib.parse import urlparse
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer

TARGET = "type"
CLASSES = ["benign", "defacement", "malware", "phishing"]
SHORTENERS = {"bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rebrand.ly"}
SUSPICIOUS = r"login|secure|account|update|bank|verify|signin|confirm|password|free|webscr|paypal|ebayisapi"

LOG_COLS = ["url_len", "n_dots", "n_hyphen", "n_digits", "n_slash", "n_special",
            "host_len", "path_len", "n_subdomains"]
NUM_COLS = ["digit_ratio", "url_entropy"]
BIN_COLS = ["has_https", "has_at", "has_ip", "is_shortened", "has_suspicious"]
CAT_COLS = ["tld", "scheme"]
FEATURE_COLS = LOG_COLS + NUM_COLS + BIN_COLS + CAT_COLS


def _host(u: str) -> str:
    t = u if u.lower().startswith("http") else "http://" + u
    try:
        return urlparse(t).netloc.split(":")[0]
    except ValueError:
        return t.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0].split(":")[0]


def _path(u: str) -> str:
    t = u if u.lower().startswith("http") else "http://" + u
    try:
        return urlparse(t).path or ""
    except ValueError:
        r = t.split("://", 1)[-1]
        return "/" + r.split("/", 1)[1] if "/" in r else ""


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s); c = Counter(s)
    return float(-sum((v / n) * np.log2(v / n) for v in c.values()))


def featurize(urls: pd.Series) -> pd.DataFrame:
    """Engineer lexical features. `tld` is left raw here; map it with apply_top_tlds()."""
    s = urls.str.strip(); low = s.str.lower()
    F = pd.DataFrame(index=s.index)
    F["url_len"] = s.str.len(); F["n_dots"] = s.str.count(r"\.")
    F["n_hyphen"] = s.str.count("-"); F["n_digits"] = s.str.count(r"\d")
    F["n_slash"] = s.str.count("/"); F["n_special"] = s.str.count(r"[@?%=&_~+]")
    host = s.map(_host)
    F["host_len"] = host.str.len(); F["path_len"] = s.map(_path).str.len()
    F["n_subdomains"] = host.str.count(r"\.")
    F["digit_ratio"] = (F["n_digits"] / F["url_len"]).fillna(0)
    F["url_entropy"] = s.map(_entropy)
    F["has_https"] = low.str.startswith("https").astype(int)
    F["has_at"] = s.str.contains("@").astype(int)
    F["has_ip"] = host.str.contains(r"^(?:\d{1,3}\.){3}\d{1,3}$", regex=True).astype(int)
    F["is_shortened"] = host.str.lower().isin(SHORTENERS).astype(int)
    F["has_suspicious"] = low.str.contains(SUSPICIOUS, regex=True).astype(int)
    F["scheme"] = np.where(low.str.startswith("https"), "https",
                           np.where(low.str.startswith("http"), "http", "none"))
    F["tld"] = host.str.rsplit(".", n=1).str[-1].str.lower().where(host.str.contains(r"\."), "none")
    return F


def apply_top_tlds(F: pd.DataFrame, top_tlds) -> pd.DataFrame:
    F = F.copy()
    F["tld"] = F["tld"].where(F["tld"].isin(set(top_tlds)), "other")
    return F


def build_preprocessor() -> ColumnTransformer:
    log_pipe = Pipeline([("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                         ("scale", StandardScaler())])
    return ColumnTransformer([
        ("log", log_pipe, LOG_COLS),
        ("num", StandardScaler(), NUM_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
        ("bin", "passthrough", BIN_COLS),
    ])
