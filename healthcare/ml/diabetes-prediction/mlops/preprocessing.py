"""Reusable preprocessing for the diabetes dataset.

Shared by the modeling notebook and (later) the live demo so training and
inference apply identical cleaning / feature engineering / transforms.

All aggregate-based steps (imputation, scaling, encoding) are fit on the
TRAINING split only to avoid data leakage.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer

RANDOM_STATE = 42
TARGET = "diabetes"
BMI_FILLER = 27.32  # equals dataset mean -> imputed placeholder, treated as missing

LOG_COLS = ["bmi", "blood_glucose_level"]      # right-skewed
PLAIN_NUM = ["age", "HbA1c_level"]
BINARY_COLS = ["hypertension", "heart_disease", "bmi_missing", "comorbidity_count"]
CAT_COLS = ["gender", "smoking_history", "hba1c_category", "glucose_category", "age_group"]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Row-wise, leakage-safe cleaning."""
    df = df.drop_duplicates().reset_index(drop=True)
    df["bmi_missing"] = (df["bmi"] == BMI_FILLER).astype(int)
    df.loc[df["bmi"] == BMI_FILLER, "bmi"] = np.nan
    df["smoking_history"] = df["smoking_history"].replace("No Info", "unknown")
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature engineering from fixed clinical thresholds (leakage-safe)."""
    d = df.copy()
    d["hba1c_category"] = pd.cut(d["HbA1c_level"], bins=[-np.inf, 5.7, 6.4, np.inf],
                                 labels=["normal", "prediabetic", "high"])
    d["glucose_category"] = pd.cut(d["blood_glucose_level"], bins=[-np.inf, 140, 199, np.inf],
                                   labels=["normal", "prediabetic", "high"])
    d["age_group"] = pd.cut(d["age"], bins=[0, 12, 18, 35, 50, 65, np.inf],
                            labels=["child", "teen", "young_adult", "adult", "middle_age", "senior"])
    d["comorbidity_count"] = d["hypertension"] + d["heart_disease"]
    return d


def build_preprocessor() -> ColumnTransformer:
    log_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
        ("scale", StandardScaler()),
    ])
    num_pipe = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    cat_pipe = Pipeline([("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    return ColumnTransformer([
        ("log", log_pipe, LOG_COLS),
        ("num", num_pipe, PLAIN_NUM),
        ("cat", cat_pipe, CAT_COLS),
        ("bin", "passthrough", BINARY_COLS),
    ])


def load_splits(csv_path: str, transform: bool = True):
    """Return an 80/10/10 stratified split.

    If transform=True, also returns transformed matrices and the fitted
    preprocessor (fit on train only). Dict keys:
      X_train, X_val, X_test, y_train, y_val, y_test,
      [X_train_t, X_val_t, X_test_t, preprocessor, feature_names]
    """
    df = add_features(clean(pd.read_csv(csv_path)))
    X, y = df.drop(columns=[TARGET]), df[TARGET]

    X_train, X_tmp, y_train, y_tmp = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE)
    X_val, X_test, y_val, y_test = train_test_split(
        X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=RANDOM_STATE)

    out = dict(X_train=X_train, X_val=X_val, X_test=X_test,
               y_train=y_train, y_val=y_val, y_test=y_test)
    if transform:
        pre = build_preprocessor()
        out["X_train_t"] = pre.fit_transform(X_train)
        out["X_val_t"] = pre.transform(X_val)
        out["X_test_t"] = pre.transform(X_test)
        out["preprocessor"] = pre
        out["feature_names"] = pre.get_feature_names_out()
    return out
