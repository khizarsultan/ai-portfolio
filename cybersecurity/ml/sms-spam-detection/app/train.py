"""Train the SMS spam classifier (TF-IDF + Logistic Regression) and bundle the
dashboard artifact. Run once:  /usr/bin/python3 train.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve

CSV = "../../../data/cybersecurity-sms-spam/sms_spam.csv"
RANDOM_STATE = 42


def _thr(y, p):
    prec, rec, t = precision_recall_curve(y, p)
    f1 = 2 * prec * rec / (prec + rec + 1e-12)
    return float(t[int(np.nanargmax(f1[:-1]))])


def main():
    df = pd.read_csv(CSV).dropna().drop_duplicates().reset_index(drop=True)
    df["y"] = (df["label"].str.lower() == "spam").astype(int)
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(df["text"], df["y"], test_size=.20, stratify=df["y"], random_state=RANDOM_STATE)
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=.50, stratify=y_tmp, random_state=RANDOM_STATE)

    vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=2,
                          stop_words="english", max_features=20000)
    Xtr = vec.fit_transform(X_tr)
    clf = LogisticRegression(class_weight="balanced", max_iter=1000, C=4.0)
    clf.fit(Xtr, y_tr)
    thr = _thr(y_val, clf.predict_proba(vec.transform(X_val))[:, 1])

    art = {
        "vectorizer": vec, "model": clf, "threshold": thr,
        "classes": ["ham (benign)", "spam (malicious)"],
        "model_name": "TF-IDF + Logistic Regression",
        "vocab": np.array(vec.get_feature_names_out()),
        "coef": clf.coef_.ravel(),
        "X_test_text": X_te.reset_index(drop=True), "y_test": y_te.reset_index(drop=True),
        "X_ref_text": X_tr.reset_index(drop=True),
    }
    joblib.dump(art, "artifact.joblib", compress=3)
    print("saved artifact.joblib | thr=%.3f | test=%d | vocab=%d" % (thr, len(y_te), len(art["vocab"])))


if __name__ == "__main__":
    main()
