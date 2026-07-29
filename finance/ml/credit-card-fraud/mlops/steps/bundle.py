"""Assemble the full dashboard artifact (bundle) the fraud Streamlit app loads."""
from __future__ import annotations
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def build(core_art: dict, ref_df, holdout_df) -> dict:
    """core_art has model/preprocessor/threshold/feature_names/model_name; attach bundled data."""
    pre = core_art["preprocessor"]
    feat = [c for c in ref_df.columns if c != C.TARGET]
    hold = holdout_df
    if len(hold) > C.TEST_SAMPLE:
        hold = hold.groupby(C.TARGET, group_keys=False).apply(
            lambda g: g.sample(min(len(g), max(1, int(C.TEST_SAMPLE * len(g) / len(holdout_df)))),
                               random_state=C.RANDOM_STATE))
    X_test_eng = hold[feat].reset_index(drop=True)
    y_test = hold[C.TARGET].reset_index(drop=True)
    ref_s = ref_df.sample(min(len(ref_df), C.REF_SAMPLE), random_state=C.RANDOM_STATE)
    bg = ref_df[feat].sample(min(len(ref_df), 200), random_state=0)
    return {
        "model": core_art["model"], "preprocessor": pre, "threshold": core_art["threshold"],
        "feature_names": core_art["feature_names"], "input_cols": feat,
        "model_name": core_art["model_name"], "classes": ["genuine", "fraud"],
        "X_test_eng": X_test_eng, "y_test": y_test,
        "X_ref_eng": ref_s[feat].reset_index(drop=True),
        "background_t": np.asarray(pre.transform(bg)),
    }
