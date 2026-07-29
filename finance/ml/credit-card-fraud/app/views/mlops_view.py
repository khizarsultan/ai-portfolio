"""MLOps Pipeline section of the unified dashboard.

A GUI over the healthcare/mlops pipeline: browse the MLflow registry, run the
drift-triggered flow, compare champion vs challenger, and approve/promote — all in
the same Streamlit app that serves the model. Heavy logic lives in healthcare/mlops.
"""
from __future__ import annotations
import os
import sys
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import ui

# make the healthcare/mlops package importable
MLOPS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mlops"))
sys.path.insert(0, MLOPS)
import config as C
from steps import registry, ingest, modeling, drift, evaluate, promote

BLUE, AQUA, YELLOW, INK, GRID, SURFACE = ui.BRAND, ui.BRAND_DEEP, ui.WARN, ui.INK, ui.LINE2, ui.SURFACE
STATUS = {"good": ui.GOOD, "warning": ui.WARN, "critical": ui.CRIT}


def _bump():
    """State changed — drop cached model so the Model Dashboard reloads the new champion."""
    st.cache_resource.clear()
    st.cache_data.clear()


def do_retrain():
    win = ingest.latest_snapshot("window")
    if win is None:
        return None, "No production window yet — draw one first."
    train_df = pd.concat([ingest.get_reference(), ingest.load_snapshot(win)], ignore_index=True)
    art = modeling.train_model(train_df, random_state=C.RANDOM_STATE)
    metrics = modeling.evaluate_artifact(art, ingest.get_holdout())
    meta = json.load(open(os.path.join(win, "meta.json")))
    v = registry.log_and_register(art, metrics, params={"n_train": len(train_df), "window": meta["version"]},
                                  dataset_meta=meta, run_name="retrain", alias=C.ALIAS_CHALLENGER)
    return {"version": v, "metrics": metrics, "window": meta["version"]}, None


st.title("Credit-Card Fraud MLOps Pipeline")
st.caption("Registry · drift-triggered retraining · champion vs challenger · manual approval · promotion")

t_reg, t_run, t_drift, t_cmp, t_appr = st.tabs(
    ["Registry & Lifecycle", "Run Pipeline", "Drift", "Champion vs Challenger", "Approvals"])

# ===================================================================== Registry
with t_reg:
    st.graphviz_chart("""digraph {rankdir=LR; bgcolor="transparent";
      node [shape=box style="rounded,filled" fillcolor="#eaf2fd" color="#2a78d6" fontname="sans-serif"];
      "new data\\n(window)" -> "drift check\\n(PSI + Evidently)" -> "retrain\\nchallenger"
      -> "evaluate\\nvs champion" -> "manual\\napproval" -> "production\\n(serving)";}""")

    prod = registry.version_by_alias(C.ALIAS_PROD)
    chal = registry.version_by_alias(C.ALIAS_CHALLENGER)
    c = st.columns(3)
    c[0].metric("Production (champion)", f"v{prod.version}" if prod else "—")
    c[1].metric("Challenger", f"v{chal.version}" if chal else "—")
    c[2].metric("Serving artifact", "present" if os.path.exists(C.SERVING_ARTIFACT) else "MISSING")

    versions = registry.list_versions()
    if versions:
        df = pd.DataFrame(versions)
        df["aliases"] = df["aliases"].map(lambda a: ", ".join(a) if a else "")
        st.dataframe(df.rename(columns={"version": "ver", "roc_auc": "ROC-AUC", "pr_auc": "PR-AUC"}),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No registered versions yet. Bootstrap the champion from the terminal: "
                "`python pipeline.py bootstrap`.")
    st.caption(f"MLflow store: `{C.TRACKING_URI}` — deep-dive UI: "
               "`mlflow ui --backend-store-uri sqlite:///mlflow.db`")

# ===================================================================== Run Pipeline
with t_run:
    st.subheader("Drift-triggered retraining")
    cc = st.columns([1, 1, 1.2], vertical_alignment="bottom")
    n = cc[0].number_input("Window size", 1000, 20000, 8000, 1000)
    inject = cc[1].checkbox("Inject drift", value=True, help="Simulate a shifted production population.")
    run_full = cc[2].button("Run full cycle", type="primary", use_container_width=True)

    if run_full:
        with st.spinner("window → drift → (retrain → evaluate)…"):
            ingest.make_window(n=int(n), drift=inject)
            res = drift.run_drift_check(ingest.get_reference(),
                                        ingest.load_snapshot(ingest.latest_snapshot("window")), tag="ui")
            st.session_state.mlops_drift = res
            if res["drifted"]:
                rec, err = do_retrain()
                if err:
                    st.error(err)
                else:
                    st.session_state.mlops_eval = evaluate.evaluate_challenger()
        _bump()
        if st.session_state.get("mlops_drift", {}).get("drifted"):
            st.success("Drift detected → challenger trained & evaluated. See **Champion vs Challenger** / **Approvals**.")
        else:
            st.info("No significant drift → retraining skipped (this is correct behavior).")

    st.divider()
    st.caption("…or run stages individually:")
    g = st.columns(4)
    if g[0].button("1 · Draw window", use_container_width=True):
        vdir = ingest.make_window(n=int(n), drift=inject)
        st.success(f"Snapshot: {os.path.basename(vdir)}")
    if g[1].button("2 · Check drift", use_container_width=True):
        win = ingest.latest_snapshot("window")
        if win is None:
            st.warning("Draw a window first.")
        else:
            st.session_state.mlops_drift = drift.run_drift_check(
                ingest.get_reference(), ingest.load_snapshot(win), tag="ui")
            st.success("Drift report ready — see the **Drift** tab.")
    if g[2].button("3 · Retrain", use_container_width=True):
        with st.spinner("training challenger…"):
            rec, err = do_retrain()
        (st.error(err) if err else st.success(f"Challenger v{rec['version']} registered "
                                              f"(ROC-AUC {rec['metrics']['roc_auc']:.4f})."))
    if g[3].button("4 · Evaluate", use_container_width=True):
        try:
            st.session_state.mlops_eval = evaluate.evaluate_challenger()
            st.success("Evaluated — see **Champion vs Challenger** / **Approvals**.")
        except Exception as e:
            st.error(str(e))

# ===================================================================== Drift
with t_drift:
    st.subheader("Data drift — latest window vs training reference")
    res = st.session_state.get("mlops_drift")
    if st.button("Run drift check now"):
        win = ingest.latest_snapshot("window")
        if win is None:
            st.warning("Draw a window in **Run Pipeline** first.")
        else:
            res = drift.run_drift_check(ingest.get_reference(), ingest.load_snapshot(win), tag="ui")
            st.session_state.mlops_drift = res
    if res:
        cols = st.columns(3)
        cols[0].metric("Drifted?", "YES" if res["drifted"] else "no")
        cols[1].metric("Share drifted", f"{res['share_of_drifted_columns']:.2f}")
        cols[2].metric("Threshold", f"{res['threshold']}")
        table = pd.DataFrame(res["columns"])
        bar = go.Figure(go.Bar(x=table["feature"], y=table["PSI"], marker_line_width=0,
                               marker_color=[STATUS["good"] if v < 0.1 else STATUS["warning"] if v < 0.25
                                             else STATUS["critical"] for v in table["PSI"]]))
        bar.add_hline(y=0.1, line=dict(color=STATUS["warning"], dash="dash"), annotation_text="watch")
        bar.add_hline(y=0.25, line=dict(color=STATUS["critical"], dash="dash"), annotation_text="drift")
        ui.style_fig(bar, h=320)
        bar.update_yaxes(title="PSI")
        st.plotly_chart(bar, use_container_width=True)
        st.dataframe(table, use_container_width=True, hide_index=True)
        if res.get("evidently_html") and os.path.exists(res["evidently_html"]):
            with st.expander("Evidently drift report (full)", expanded=False):
                components.html(open(res["evidently_html"]).read(), height=600, scrolling=True)
    else:
        st.info("No drift check yet. Run one here or via **Run Pipeline**.")

# ===================================================================== Compare
with t_cmp:
    st.subheader("Champion vs Challenger (holdout)")
    rec = st.session_state.get("mlops_eval") or evaluate.load_pending()
    if not rec:
        st.info("No evaluation yet. Run **Evaluate** in the Run Pipeline tab.")
    else:
        cm, pm = rec["challenger_metrics"], rec["champion_metrics"]
        keys = ["roc_auc", "pr_auc", "recall", "precision", "f1"]
        fig = go.Figure()
        fig.add_bar(name=f"Challenger v{rec['challenger_version']}", x=keys, y=[cm[k] for k in keys], marker_color=BLUE)
        if pm:
            fig.add_bar(name=f"Champion v{rec['champion_version']}", x=keys, y=[pm[k] for k in keys], marker_color=AQUA)
        ui.style_fig(fig, h=360)
        fig.update_layout(barmode="group")
        fig.update_yaxes(range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Promotion gate**")
        for r in rec["gate_reasons"]:
            st.write("• " + r)
        (st.success if rec["gate_passed"] else st.error)(
            "GATE PASSED → eligible for approval" if rec["gate_passed"] else "GATE FAILED → not promotable")

# ===================================================================== Approvals
with t_appr:
    st.subheader("Manual approval gate")
    pend = evaluate.load_pending()
    if not pend:
        st.info("Nothing awaiting approval. Train + evaluate a challenger first.")
    elif not pend["gate_passed"]:
        st.error(f"Challenger v{pend['challenger_version']} FAILED the automated gate — it cannot be promoted.")
        if st.button("Dismiss (reject)"):
            promote.promote(approve=False, approver="reviewer", reason="failed gate")
            st.rerun()
    else:
        st.warning(f"Challenger **v{pend['challenger_version']}** passed the gate and is awaiting sign-off "
                   f"(current champion: v{pend['champion_version']}).")
        approver = st.text_input("Approver", value="")
        reason = st.text_input("Reason / notes", value="Meets gate; drift-triggered retrain.")
        a, b, _ = st.columns([1, 1, 3])
        if a.button("Approve & promote", type="primary", use_container_width=True):
            if not approver.strip():
                st.warning("Enter an approver name before promoting.")
                st.stop()
            entry = promote.promote(approve=True, approver=approver, reason=reason)
            _bump()
            st.success(f"v{entry['challenger_version']} promoted to PRODUCTION and now live in the Model Dashboard.")
            st.rerun()
        if b.button("Reject", use_container_width=True):
            promote.promote(approve=False, approver=approver, reason=reason or "rejected")
            st.rerun()

    apath = os.path.join(C.STATE_DIR, "approvals.jsonl")
    if os.path.exists(apath):
        st.markdown("**Audit trail**")
        rows = [json.loads(l) for l in open(apath) if l.strip()]
        st.dataframe(pd.DataFrame(rows)[::-1], use_container_width=True, hide_index=True)
