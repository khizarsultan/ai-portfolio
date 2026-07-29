"""Train the multi-class URL model and bundle everything the dashboard needs.

Deploys the cost-sensitive model (class_weight='balanced') — the security-recommended
choice from 02_modeling (best recall on malware & phishing). Run once, offline:

    /usr/bin/python3 train.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier

from features import (featurize, apply_top_tlds, build_preprocessor,
                      FEATURE_COLS, TARGET, CLASSES)

CSV = "../../data/cybersecurity-malicious-urls/malicious_phish.csv"
RANDOM_STATE = 42
TEST_SAMPLE = 15000
REF_SAMPLE = 15000


def main():
    df = pd.read_csv(CSV).drop_duplicates().reset_index(drop=True)
    df["url"] = df["url"].str.strip()
    bad = df.groupby("url")[TARGET].nunique()
    df = df[~df["url"].isin(bad[bad > 1].index)].reset_index(drop=True)

    F = featurize(df["url"])
    F[TARGET] = df[TARGET].values
    urls = df["url"].values

    idx = np.arange(len(F))
    tr_i, tmp_i = train_test_split(idx, test_size=.20, stratify=F[TARGET], random_state=RANDOM_STATE)
    val_i, te_i = train_test_split(tmp_i, test_size=.50, stratify=F[TARGET].iloc[tmp_i], random_state=RANDOM_STATE)

    # top TLDs from the TRAINING split only (leakage-safe), then map every split
    top_tlds = list(F.iloc[tr_i]["tld"].value_counts().head(15).index)
    F = apply_top_tlds(F, top_tlds)

    X = F[FEATURE_COLS]; y = F[TARGET]
    X_tr, y_tr = X.iloc[tr_i], y.iloc[tr_i]

    pre = build_preprocessor()
    X_tr_t = pre.fit_transform(X_tr)
    model = HistGradientBoostingClassifier(max_iter=200, class_weight="balanced", random_state=RANDOM_STATE)
    model.fit(X_tr_t, y_tr)

    # stratified test sample for fast dashboard metrics
    te = F.iloc[te_i].copy()
    te_s = te.groupby(TARGET, group_keys=False).apply(
        lambda g: g.sample(min(len(g), max(1, int(TEST_SAMPLE * len(g) / len(te)))), random_state=RANDOM_STATE))
    X_test_eng, y_test = te_s[FEATURE_COLS].reset_index(drop=True), te_s[TARGET].reset_index(drop=True)

    rng = np.random.RandomState(RANDOM_STATE)
    bg_idx = rng.choice(len(X_tr_t), size=min(150, len(X_tr_t)), replace=False)

    # a few real example URLs per class for the demo's quick-fill buttons
    examples = {c: df.iloc[te_i][df.iloc[te_i][TARGET] == c]["url"].head(3).tolist() for c in CLASSES}

    artifact = {
        "model": model,
        "preprocessor": pre,
        "feature_names": list(pre.get_feature_names_out()),
        "input_cols": FEATURE_COLS,
        "classes": list(model.classes_),
        "model_name": "HistGradientBoosting (cost-sensitive, multi-class)",
        "top_tlds": top_tlds,
        "X_test_eng": X_test_eng,
        "y_test": y_test,
        "X_ref_eng": X.iloc[tr_i].sample(min(REF_SAMPLE, len(tr_i)), random_state=RANDOM_STATE).reset_index(drop=True),
        "background_t": np.asarray(X_tr_t)[bg_idx],
        "examples": examples,
    }
    joblib.dump(artifact, "artifact.joblib", compress=3)
    print("saved artifact.joblib | classes=%s | test sample=%d | features=%d"
          % (list(model.classes_), len(y_test), len(artifact["feature_names"])))
    print("test class mix:", y_test.value_counts().to_dict())


if __name__ == "__main__":
    main()
