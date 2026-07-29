"""Train the fraud model and bundle everything the dashboard needs into artifact.joblib.

Deploys the cost-sensitive model (class_weight='balanced') — the production-recommended
choice from 02_modeling: strong recall with no synthetic data. Run once, offline:

    /usr/bin/python3 train.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import precision_recall_curve

from features import add_features, build_preprocessor, TARGET

CSV = "../../data/finance-credit-card-fraud/creditcard.csv"
RANDOM_STATE = 42
TEST_SAMPLE = 20000     # rows bundled for the dashboard's live metrics
REF_SAMPLE = 20000      # train rows bundled as the drift reference


def best_threshold(y_true, proba):
    prec, rec, thr = precision_recall_curve(y_true, proba)
    f1 = 2 * prec * rec / (prec + rec + 1e-12)
    return float(thr[int(np.nanargmax(f1[:-1]))])


def main():
    df = add_features(pd.read_csv(CSV).drop_duplicates().reset_index(drop=True))
    feat = [c for c in df.columns if c != TARGET]
    X, y = df[feat], df[TARGET]

    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=.20, stratify=y, random_state=RANDOM_STATE)
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=.50, stratify=y_tmp, random_state=RANDOM_STATE)

    pre = build_preprocessor(feat)
    X_tr_t = pre.fit_transform(X_tr)
    model = HistGradientBoostingClassifier(max_iter=200, class_weight="balanced", random_state=RANDOM_STATE)
    model.fit(X_tr_t, y_tr)

    thr = best_threshold(y_val, model.predict_proba(pre.transform(X_val))[:, 1])

    # stratified test sample for fast dashboard metrics (keep all fraud + sampled genuine)
    te = X_te.copy(); te[TARGET] = y_te.values
    fraud = te[te[TARGET] == 1]
    genuine = te[te[TARGET] == 0].sample(min(TEST_SAMPLE - len(fraud), (te[TARGET] == 0).sum()),
                                         random_state=RANDOM_STATE)
    te_s = pd.concat([fraud, genuine]).sample(frac=1, random_state=RANDOM_STATE)
    X_test_eng, y_test = te_s[feat].reset_index(drop=True), te_s[TARGET].reset_index(drop=True)

    rng = np.random.RandomState(RANDOM_STATE)
    bg_idx = rng.choice(len(X_tr_t), size=min(200, len(X_tr_t)), replace=False)

    artifact = {
        "model": model,
        "preprocessor": pre,
        "threshold": thr,
        "feature_names": list(pre.get_feature_names_out()),
        "input_cols": feat,
        "model_name": "HistGradientBoosting (cost-sensitive)",
        "classes": ["genuine", "fraud"],
        "X_test_eng": X_test_eng,
        "y_test": y_test,
        "X_ref_eng": X_tr.sample(min(REF_SAMPLE, len(X_tr)), random_state=RANDOM_STATE).reset_index(drop=True),
        "background_t": np.asarray(X_tr_t)[bg_idx],
    }
    joblib.dump(artifact, "artifact.joblib", compress=3)
    print("saved artifact.joblib | threshold=%.4f | test sample=%d (%d fraud) | features=%d"
          % (thr, len(y_test), int(y_test.sum()), len(artifact["feature_names"])))


if __name__ == "__main__":
    main()
