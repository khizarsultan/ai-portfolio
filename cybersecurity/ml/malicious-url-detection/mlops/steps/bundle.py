"""Assemble the full dashboard artifact the URL-threat Streamlit app loads."""
from __future__ import annotations
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from features import FEATURE_COLS
from steps import ingest

EXAMPLES = {
    "benign": ["mp3raid.com/music/krizz_kaliko.html"],
    "defacement": ["http://www.garage-pirenne.be/index.php?option=com_content&view=article&id=70"],
    "malware": ["http://www.824555.com/app/member/SportOption.php?uid=guest&langx=gb"],
    "phishing": ["http://br-icloud.com.br/login/verify-account.php"],
}


def build(core_art: dict, ref_df, holdout_df) -> dict:
    pre = core_art["preprocessor"]
    hold = holdout_df
    if len(hold) > C.TEST_SAMPLE:
        hold = hold.groupby(C.TARGET, group_keys=False).apply(
            lambda g: g.sample(min(len(g), max(1, int(C.TEST_SAMPLE * len(g) / len(holdout_df)))),
                               random_state=C.RANDOM_STATE))
    ref_s = ref_df.sample(min(len(ref_df), C.REF_SAMPLE), random_state=C.RANDOM_STATE)
    return {
        "model": core_art["model"], "preprocessor": pre,
        "feature_names": core_art["feature_names"], "input_cols": FEATURE_COLS,
        "classes": list(core_art["model"].classes_), "model_name": core_art["model_name"],
        "top_tlds": ingest.get_top_tlds(),
        "X_test_eng": hold[FEATURE_COLS].reset_index(drop=True),
        "y_test": hold[C.TARGET].reset_index(drop=True),
        "X_ref_eng": ref_s[FEATURE_COLS].reset_index(drop=True),
        "background_t": np.asarray(pre.transform(ref_df[FEATURE_COLS].sample(min(len(ref_df), 150), random_state=0))),
        "examples": EXAMPLES,
    }
