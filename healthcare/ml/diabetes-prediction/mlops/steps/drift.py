"""Data-drift detection.

The retraining TRIGGER is a deterministic PSI computation (fully under our control, so
the pipeline is reproducible and dependency-robust). Evidently additionally renders a
rich HTML drift report as a governance artifact when it is available — best-effort, so a
library/version hiccup never breaks the pipeline.

A column is "drifted" when PSI ≥ 0.1; the dataset is drifted when the share of drifted
columns exceeds config.DRIFT_SHARE_THRESHOLD.
"""
from __future__ import annotations
import os
import sys
import json
import datetime as dt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

_COL_DRIFT_PSI = 0.1


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    ref = reference[~np.isnan(reference)]
    cur = current[~np.isnan(current)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    q = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(q) < 3:
        return 0.0
    q[0], q[-1] = -np.inf, np.inf
    r = np.clip(np.histogram(ref, bins=q)[0] / len(ref), 1e-6, None)
    c = np.clip(np.histogram(cur, bins=q)[0] / len(cur), 1e-6, None)
    return float(np.sum((c - r) * np.log(c / r)))


def psi_table(reference_df: pd.DataFrame, current_df: pd.DataFrame, cols=None) -> pd.DataFrame:
    cols = cols or C.DRIFT_COLS
    rows = []
    for col in cols:
        val = psi(reference_df[col].values.astype(float), current_df[col].values.astype(float))
        status = "OK" if val < _COL_DRIFT_PSI else ("WARNING" if val < 0.25 else "DRIFT")
        rows.append({"feature": col, "PSI": round(val, 4), "status": status})
    return pd.DataFrame(rows)


def _evidently_html(reference_df, current_df, cols, out_html: str) -> str | None:
    """Best-effort Evidently DataDrift HTML report; returns path or None."""
    try:
        from evidently import Report
        try:
            from evidently.presets import DataDriftPreset
        except Exception:
            from evidently.metric_preset import DataDriftPreset
        rep = Report(metrics=[DataDriftPreset()])
        res = rep.run(reference_data=reference_df[cols], current_data=current_df[cols])
        obj = res if hasattr(res, "save_html") else rep
        obj.save_html(out_html)
        return out_html
    except Exception:
        return None


def run_drift_check(reference_df: pd.DataFrame, current_df: pd.DataFrame,
                    cols=None, tag: str = "") -> dict:
    cols = cols or C.DRIFT_COLS
    table = psi_table(reference_df, current_df, cols)
    share = float((table["PSI"] >= _COL_DRIFT_PSI).mean())
    drifted = share > C.DRIFT_SHARE_THRESHOLD

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(C.REPORTS_DIR, f"drift-{tag or stamp}")
    summary = {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "drifted": bool(drifted),
        "share_of_drifted_columns": round(share, 3),
        "threshold": C.DRIFT_SHARE_THRESHOLD,
        "columns": table.to_dict(orient="records"),
        "n_reference": len(reference_df), "n_current": len(current_df),
    }
    with open(base + ".json", "w") as f:
        json.dump(summary, f, indent=2)
    html = _evidently_html(reference_df, current_df, cols, base + ".html")
    summary["evidently_html"] = html
    summary["json_report"] = base + ".json"
    return summary
