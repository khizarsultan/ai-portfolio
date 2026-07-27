"""Khizar Sultan — ML & MLOps showcase dashboard (Diabetes risk model).

A single Streamlit app that lets a stakeholder, in one place:
  • run a live prediction and see WHY the model decided that (SHAP, local),
  • judge model quality (ROC/PR AUC, precision/recall, confusion, curves),
  • understand what drives the model globally (SHAP, global),
  • watch operational health (latency p50/p95/p99, throughput, memory, CPU),
  • monitor data drift (PSI) before it silently degrades accuracy.

All computation lives in core.py; this file is presentation only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
import ui

# Design tokens imported from the shared design system (OCR Benchmark project).
BLUE, AQUA, YELLOW = ui.BRAND, ui.BRAND_DEEP, ui.WARN
INK, MUTED, GRID, SURFACE = ui.INK, ui.MUTED, ui.LINE2, ui.SURFACE
STATUS = {"good": ui.GOOD, "warning": ui.WARN, "serious": "#c98a00", "critical": ui.CRIT}
POS, NEG = ui.POS, ui.NEG               # SHAP: raises risk (red) / lowers risk (blue)
BLUE_SEQ = ui.BLUE_SEQ                   # sequential blue for heatmaps


def _style(fig, h=360, title=None):
    return ui.style_fig(fig, h=h, title=title)


def pretty(name: str) -> str:
    """Turn a transformed feature name (log__bmi) into a readable label."""
    for p in ("log__", "num__", "cat__", "bin__", "remainder__"):
        name = name.replace(p, "")
    return name.replace("_", " ").strip()


@st.cache_data(show_spinner=False)
def what_if(_art, patient_items, feature):
    return core.what_if_curve(_art, dict(patient_items), feature)


# --------------------------------------------------------------------------
# Cached loaders — model, data, SHAP explainer, and expensive computations.
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading model & data…")
def load_all():
    return core.load_artifact(), core.get_data()


@st.cache_resource(show_spinner="Building SHAP explainer…")
def get_explainer(_model, X_bg):
    return core.build_explainer(_model, X_bg)


@st.cache_data(show_spinner="Scoring test set…")
def perf(_model, X_te, y_te, threshold):
    return core.performance_metrics(_model, X_te, y_te, threshold)


@st.cache_data(show_spinner="Computing global explanations…")
def global_shap(_expl, X_sample, feature_names):
    exp = core.shap_values_pos(_expl, X_sample)
    return core.global_importance(exp, feature_names), exp.values


@st.cache_data(show_spinner="Benchmarking latency…")
def bench(_model, X_sample):
    return core.benchmark_latency(_model, X_sample, n=200)


art, data = load_all()
model, threshold_default = art["model"], art["threshold"]
feat_names = art["feature_names"]
X_te_t, y_te = data["X_test_t"], data["y_test"]

st.title("Diabetes Risk — ML & MLOps Dashboard")
st.caption(f"**{art['model_name']}** · trained on 100k patient records — model quality, "
           "explainability, and live operational health in one view.")

# Inline control (above the content, not in a sidebar): drives the KPIs and tabs live.
ctl = st.columns([1.4, 2.6])
with ctl[0]:
    threshold = st.slider(
        "Decision threshold", 0.05, 0.95, float(round(threshold_default, 2)), 0.01,
        help="Probability cut-off for flagging a patient as high-risk. Lower = higher recall; "
             f"higher = fewer false alarms. Model-tuned default {threshold_default:.3f}.")

m = perf(model, X_te_t, y_te, threshold)
lat = art.get("latency") or bench(model, X_te_t)
res = core.resource_usage()

k = st.columns(6)
k[0].metric("ROC-AUC", f"{m['scores']['ROC_AUC']:.3f}")
k[1].metric("PR-AUC", f"{m['scores']['PR_AUC']:.3f}",
            help="Area under precision-recall — the honest metric under class imbalance.")
k[2].metric("Recall", f"{m['scores']['Recall']:.1%}",
            help="Share of true diabetics the model catches at this threshold.")
k[3].metric("Precision", f"{m['scores']['Precision']:.1%}")
k[4].metric("p95 latency", f"{lat['p95']:.1f} ms")
k[5].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")

tab_pred, tab_perf, tab_xai, tab_ops, tab_drift = st.tabs(
    ["Predict & Explain", "Performance", "Explainability",
     "System & Ops", "Data Drift"])

# ======================================================================
# TAB 1 — Live prediction + per-decision SHAP explanation (local XAI)
# ======================================================================
with tab_pred:
    st.subheader("Score a patient and see why")

    def _score(inp):
        expl = get_explainer(model, data["X_train_t"])
        row = art["preprocessor"].transform(core.raw_to_frame(inp))
        st.session_state.patient_inp = inp
        st.session_state.pred_p = core.predict_proba_raw(art, inp)
        st.session_state.pred_contrib = core.local_contributions(
            core.shap_values_pos(expl, row), feat_names)

    # Show a worked example on first load — use precomputed SHAP (instant, no explainer build).
    if "patient_inp" not in st.session_state:
        dfp = art.get("default_inp") or dict(gender="Female", age=54, hypertension=0, heart_disease=0,
                                             smoking_history="never", bmi=28.5, HbA1c_level=6.2, blood_glucose_level=145)
        if art.get("default_contrib") is not None:
            st.session_state.patient_inp = dfp
            st.session_state.pred_p = core.predict_proba_raw(art, dfp)
            st.session_state.pred_contrib = art["default_contrib"]
        else:
            _score(dfp)

    # Inputs — full-width, compact (no dead column)
    with st.form("patient"):
        g = st.columns(4)
        gender = g[0].selectbox("Gender", ["Female", "Male", "Other"])
        age = g[1].number_input("Age", 1, 100, 54)
        bmi = g[2].number_input("BMI", 10.0, 60.0, 28.5, 0.1)
        hba1c = g[3].number_input("HbA1c level", 3.0, 15.0, 6.2, 0.1)
        g2 = st.columns(4, vertical_alignment="bottom")
        glucose = g2[0].number_input("Blood glucose", 50, 400, 145)
        smoking = g2[1].selectbox("Smoking history",
                                  ["never", "former", "current", "not current", "ever", "unknown"])
        hyper = g2[2].checkbox("Hypertension")
        heart = g2[3].checkbox("Heart disease")
        submitted = st.form_submit_button("Predict risk", type="primary")
    if submitted:
        _score(dict(gender=gender, age=int(age), hypertension=int(hyper),
                    heart_disease=int(heart), smoking_history=smoking,
                    bmi=float(bmi), HbA1c_level=float(hba1c), blood_glucose_level=int(glucose)))
    st.caption("Showing a sample patient — edit the values and click **Predict risk** to update.")

    patient = st.session_state.get("patient_inp")
    if patient:
        p = st.session_state.pred_p
        flag = p >= threshold
        r1, r2 = st.columns([1, 1.4], gap="large")
        with r1:
            gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=p * 100,
                number={"suffix": "%", "font": {"size": 40}},
                gauge={"axis": {"range": [0, 100]},
                       "bar": {"color": STATUS["critical"] if flag else STATUS["good"]},
                       "threshold": {"line": {"color": INK, "width": 3},
                                     "value": threshold * 100},
                       "steps": [{"range": [0, threshold * 100], "color": "#eafaea"},
                                 {"range": [threshold * 100, 100], "color": "#fdeaea"}]}))
            st.plotly_chart(_style(gauge, 240, "Predicted probability of diabetes"),
                            use_container_width=True)
            (st.error if flag else st.success)(
                f"**{'High' if flag else 'Low'} risk** — {p:.1%} "
                f"{'≥' if flag else '<'} threshold {threshold:.0%}")
        with r2:
            contrib = st.session_state.pred_contrib.head(10).iloc[::-1]
            bar = go.Figure(go.Bar(
                x=contrib["shap"], y=[pretty(f) for f in contrib["feature"]],
                orientation="h",
                marker_color=[POS if v > 0 else NEG for v in contrib["shap"]],
                marker_line_width=0))
            bar.add_vline(x=0, line_color=MUTED, line_width=1)
            st.plotly_chart(
                _style(bar, 340, "Why (1) — SHAP: top drivers of this prediction"),
                use_container_width=True)
            st.caption("Red bars push risk up; blue bars push risk down "
                       "(SHAP contribution to this patient's score).")

        st.divider()
        w1, w2 = st.columns(2, gap="large")
        LBL = {"HbA1c level": "HbA1c_level", "Blood glucose": "blood_glucose_level",
               "BMI": "bmi", "Age": "age"}
        with w1:
            st.markdown("**Why (2) — What-if: how this patient's risk responds**")
            choice = st.selectbox("Vary one clinical value (all else held fixed)",
                                  list(LBL), key="whatif_feat")
            fk = LBL[choice]
            xs, ys = what_if(art, tuple(sorted(patient.items())), fk)
            line = go.Figure()
            line.add_trace(go.Scatter(x=xs, y=ys * 100, mode="lines",
                                      line=dict(color=BLUE, width=3), name="risk"))
            line.add_hline(y=threshold * 100, line=dict(color=MUTED, width=1, dash="dash"),
                           annotation_text="decision threshold")
            line.add_trace(go.Scatter(x=[patient[fk]], y=[st.session_state.pred_p * 100],
                                      mode="markers", name="this patient",
                                      marker=dict(color=STATUS["critical"], size=12,
                                                  line=dict(color="#fff", width=2))))
            line.update_xaxes(title=choice)
            line.update_yaxes(title="predicted risk %", range=[0, 100])
            _style(line, 320, f"Risk vs {choice}")
            line.update_layout(showlegend=False)
            st.plotly_chart(line, use_container_width=True)
            st.caption("The model re-scored this exact patient at each value — the dot marks where "
                       "they are now (Individual Conditional Expectation).")
        with w2:
            st.markdown("**Why (3) — What would change the decision**")
            st.caption("Smallest single change that flips the current decision (others fixed).")
            for fk, (lo, hi, label) in core.CLINICAL_RANGES.items():
                xs, ys = what_if(art, tuple(sorted(patient.items())), fk)
                cur = float(patient[fk])
                crossings = core.threshold_crossings(xs, ys, threshold)
                dec = 0 if fk in ("age", "blood_glucose_level") else 1
                if crossings:
                    x = min(crossings, key=lambda z: abs(z - cur))
                    arrow = "≥" if x > cur else "≤"
                    st.markdown(f"- **{label}** {arrow} **{x:.{dec}f}** flips it "
                                f"(now {cur:.{dec}f}).")
                else:
                    st.markdown(f"- **{label}** — no change in range flips it (now {cur:.{dec}f}).")
            st.caption("A counterfactual: the actionable threshold for each clinical value.")

# ======================================================================
# TAB 2 — Model performance (threshold-aware)
# ======================================================================
with tab_perf:
    st.subheader(f"Performance @ threshold {threshold:.2f}")
    s = m["scores"]
    cols = st.columns(6)
    for col, (label, val) in zip(cols, [
            ("Accuracy", s["Accuracy"]), ("Precision", s["Precision"]),
            ("Recall", s["Recall"]), ("F1", s["F1"]),
            ("ROC-AUC", s["ROC_AUC"]), ("PR-AUC", s["PR_AUC"])]):
        col.metric(label, f"{val:.3f}")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        cm = m["confusion"]
        hm = go.Figure(go.Heatmap(
            z=cm, x=["Pred: No", "Pred: Yes"], y=["True: No", "True: Yes"],
            colorscale=BLUE_SEQ, showscale=False,
            text=cm, texttemplate="%{text}", textfont={"size": 18}))
        st.plotly_chart(_style(hm, 340, "Confusion matrix"), use_container_width=True)
    with c2:
        fpr, tpr = m["roc"]
        roc = go.Figure()
        roc.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines",
                                 line=dict(color=BLUE, width=2), name="Model"))
        roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                 line=dict(color=MUTED, width=1, dash="dash"),
                                 name="Random"))
        roc.update_xaxes(title="False positive rate")
        roc.update_yaxes(title="True positive rate")
        st.plotly_chart(_style(roc, 340, f"ROC curve · AUC {s['ROC_AUC']:.3f}"),
                        use_container_width=True)

    rec, prec = m["pr"]
    pr = go.Figure()
    pr.add_trace(go.Scatter(x=rec, y=prec, mode="lines",
                            line=dict(color=AQUA, width=2), name="Model"))
    pr.add_hline(y=m["baseline"], line=dict(color=MUTED, width=1, dash="dash"),
                 annotation_text=f"Prevalence {m['baseline']:.1%}")
    pr.update_xaxes(title="Recall")
    pr.update_yaxes(title="Precision")
    st.plotly_chart(_style(pr, 340, f"Precision-Recall curve · AP {s['PR_AUC']:.3f}"),
                    use_container_width=True)

# ======================================================================
# TAB 3 — Global explainability
# ======================================================================
with tab_xai:
    st.subheader("What drives the model, globally")
    st.caption("Mean absolute SHAP value per feature over a sample of the test set — "
               "the model's overall reasoning, not one patient's.")
    imp = art.get("global_importance")
    if imp is None:
        imp = global_shap(get_explainer(model, data["X_train_t"]), X_te_t[:120], feat_names)[0]
    top = imp.head(15).iloc[::-1]
    bar = go.Figure(go.Bar(x=top["importance"], y=[pretty(f) for f in top["feature"]],
                           orientation="h", marker_color=BLUE, marker_line_width=0))
    st.plotly_chart(_style(bar, 480, "Global feature importance (mean |SHAP|)"),
                    use_container_width=True)
    with st.expander("Full importance table"):
        st.dataframe(imp.assign(feature=imp["feature"].map(pretty))
                     .rename(columns={"importance": "mean |SHAP|"}),
                     use_container_width=True, hide_index=True)

# ======================================================================
# TAB 4 — System & operational metrics
# ======================================================================
with tab_ops:
    st.subheader("Operational health")
    st.caption("Live inference latency, throughput, and resource footprint — "
               "what a production SRE watches.")
    c = st.columns(4)
    c[0].metric("p50 latency", f"{lat['p50']:.2f} ms")
    c[1].metric("p95 latency", f"{lat['p95']:.2f} ms")
    c[2].metric("p99 latency", f"{lat['p99']:.2f} ms")
    c[3].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")

    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        hist = go.Figure(go.Histogram(x=lat["latencies_ms"], nbinsx=40,
                                      marker_color=BLUE, marker_line_width=0))
        for q, lab in [("p50", STATUS["good"]), ("p95", YELLOW), ("p99", STATUS["critical"])]:
            hist.add_vline(x=lat[q], line=dict(color=lab, width=2, dash="dash"),
                           annotation_text=q)
        hist.update_xaxes(title="Single-row inference latency (ms)")
        hist.update_yaxes(title="Count")
        st.plotly_chart(_style(hist, 360, "Latency distribution (200 requests)"),
                        use_container_width=True)
    with c2:
        r = st.columns(2)
        r[0].metric("Process memory", f"{res['process_mem_mb']:.0f} MB")
        r[1].metric("System memory", f"{res['system_mem_pct']:.0f} %")
        r[0].metric("CPU load", f"{res['cpu_pct']:.0f} %")
        r[1].metric("CPU cores", f"{res['n_cores']}")
        st.caption("Footprint measured on the serving host in real time.")

# ======================================================================
# TAB 5 — Data drift monitoring (PSI)
# ======================================================================
with tab_drift:
    st.subheader("Data drift — Population Stability Index")
    st.caption("Compares live/serving data against the training distribution. "
               "PSI < 0.1 stable · 0.1–0.25 watch · > 0.25 drifted (retrain).")
    ref, cur = data["X_train"], data["X_test"].copy()
    shift_col = st.selectbox("Simulate a distribution shift on",
                             ["(none)", "age", "bmi", "HbA1c_level", "blood_glucose_level"])
    if shift_col != "(none)":
        pct = st.slider("Shift the serving distribution by", -50, 100, 30, 5,
                        format="%d%%")
        cur[shift_col] = cur[shift_col] * (1 + pct / 100.0)
        st.caption(f"Injected a {pct:+d}% shift on **{shift_col}** to demonstrate detection.")

    rep = core.drift_report(ref, cur)
    rep_show = rep.assign(feature=rep["feature"].map(pretty))
    st.dataframe(rep_show, use_container_width=True, hide_index=True)

    bar = go.Figure(go.Bar(
        x=rep["feature"].map(pretty), y=rep["PSI"], marker_line_width=0,
        marker_color=[STATUS["good"] if v < 0.1 else STATUS["warning"] if v < 0.25
                      else STATUS["critical"] for v in rep["PSI"]]))
    bar.add_hline(y=0.1, line=dict(color=STATUS["warning"], width=1, dash="dash"),
                  annotation_text="watch")
    bar.add_hline(y=0.25, line=dict(color=STATUS["critical"], width=1, dash="dash"),
                  annotation_text="drift")
    bar.update_yaxes(title="PSI")
    st.plotly_chart(_style(bar, 340, "PSI by feature"), use_container_width=True)
