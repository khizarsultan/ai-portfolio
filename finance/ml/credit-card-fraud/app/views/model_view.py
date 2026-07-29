"""Khizar Sultan — Credit-Card Fraud MLOps dashboard.

Because the features are PCA-anonymized (V1..V28), a stakeholder can't hand-type a
transaction — so the Predict tab lets you draw a real transaction from the held-out
test set and explains that specific decision with SHAP. Five views: predict, evaluate,
explain, operate, monitor. Computation lives in core.py; this file is presentation only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
import ui

BLUE, AQUA, YELLOW = ui.BRAND, ui.BRAND_DEEP, ui.WARN
INK, MUTED, GRID, SURFACE = ui.INK, ui.MUTED, ui.LINE2, ui.SURFACE
STATUS = {"good": ui.GOOD, "warning": ui.WARN, "critical": ui.CRIT}
POS, NEG = ui.POS, ui.NEG
BLUE_SEQ = ui.BLUE_SEQ


def _style(fig, h=360, title=None):
    return ui.style_fig(fig, h=h, title=title)


def pretty(name: str) -> str:
    for p in ("num__", "cat__", "bin__", "log__"):
        name = name.replace(p, "")
    return name.replace("_", " ").strip()


@st.cache_resource(show_spinner="Loading model & test data…")
def load():
    art = core.load_artifact()
    return art, core.transform(art, art["X_test_eng"])


@st.cache_resource(show_spinner="Preparing explainer…")
def get_expl(_art):
    return core.build_explainer(_art["model"], _art["background_t"])


@st.cache_data(show_spinner="Scoring test set…")
def perf(_model, _Xt, y, threshold):
    return core.performance_metrics(_model, _Xt, y, threshold)


@st.cache_data(show_spinner=False)
def proba_all(_model, _Xt):
    return _model.predict_proba(_Xt)[:, 1]


@st.cache_data(show_spinner="Benchmarking…")
def bench(_model, _Xt):
    return core.benchmark_latency(_model, _Xt, n=200)


@st.cache_data(show_spinner="Computing global explanations…")
def global_shap(_expl, _Xs, feature_names):
    exp = core.shap_values_pos(_expl, _Xs)
    return core.global_importance(exp, feature_names)


art, X_test_t = load()
model, feat_names = art["model"], art["feature_names"]
X_eng, y_test = art["X_test_eng"], art["y_test"]
p_all = proba_all(model, X_test_t)

st.title("Credit-Card Fraud — ML & MLOps Dashboard")
st.caption(f"**{art['model_name']}** · {len(y_test):,} test transactions ({int(y_test.sum())} fraud) "
           "— detection quality, explanations, and live ops health.")
ctl = st.columns([1.4, 2.6])
with ctl[0]:
    threshold = st.slider("Decision threshold", 0.05, 0.99, float(round(art["threshold"], 2)), 0.01,
                          help=f"Probability cut-off for flagging fraud. Model-tuned default {art['threshold']:.3f}.")

m = perf(model, X_test_t, y_test, threshold)
lat = art.get("latency") or bench(model, X_test_t)
res = core.resource_usage()

k = st.columns(6)
k[0].metric("PR-AUC", f"{m['scores']['PR_AUC']:.3f}", help="Honest metric under 0.17% fraud prevalence.")
k[1].metric("ROC-AUC", f"{m['scores']['ROC_AUC']:.3f}")
k[2].metric("Recall", f"{m['scores']['Recall']:.1%}", help="Share of fraud caught at this threshold.")
k[3].metric("Precision", f"{m['scores']['Precision']:.1%}")
k[4].metric("p95 latency", f"{lat['p95']:.1f} ms")
k[5].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")

tab_pred, tab_perf, tab_xai, tab_ops, tab_drift = st.tabs(
    ["Predict & Explain", "Performance", "Explainability", "System & Ops", "Data Drift"])

# ---------------------------------------------------------------- Predict
with tab_pred:
    st.subheader("Draw a transaction and see why the model scored it")
    c0 = st.columns([1, 1, 1, 1])
    mode = c0[0].radio("Pick", ["Random fraud", "Random genuine", "Highest-risk"], label_visibility="collapsed")
    if c0[1].button("Draw transaction", type="primary", use_container_width=True) or "idx" not in st.session_state:
        if mode == "Random fraud" and y_test.sum() > 0:
            pool = np.where(y_test.values == 1)[0]
        elif mode == "Random genuine":
            pool = np.where(y_test.values == 0)[0]
        else:
            pool = [int(np.argmax(p_all))]
        st.session_state.idx = int(np.random.choice(pool))
    i = st.session_state.idx

    p = float(p_all[i])
    flag = p >= threshold
    actual = "FRAUD" if y_test.iloc[i] == 1 else "genuine"
    c1, c2 = st.columns([1, 1.4], gap="large")
    with c1:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=p * 100, number={"suffix": "%", "font": {"size": 40}},
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": STATUS["critical"] if flag else STATUS["good"]},
                   "threshold": {"line": {"color": INK, "width": 3}, "value": threshold * 100},
                   "steps": [{"range": [0, threshold * 100], "color": "#eafaea"},
                             {"range": [threshold * 100, 100], "color": "#fdeaea"}]}))
        st.plotly_chart(_style(gauge, 240, "Predicted probability of fraud"), use_container_width=True)
        (st.error if flag else st.success)(
            f"Model: **{'FRAUD' if flag else 'genuine'}** ({p:.1%})  ·  Actual label: **{actual}**")
        row = X_eng.iloc[i]
        st.dataframe(pd.DataFrame({
            "field": ["Amount", "hour", "amount_bin", "V14", "V17", "V12", "V10"],
            "value": [f"${row['Amount']:.2f}", str(int(row["hour"])), str(row["amount_bin"]),
                      f"{row['V14']:.2f}", f"{row['V17']:.2f}", f"{row['V12']:.2f}", f"{row['V10']:.2f}"]},
        ), hide_index=True, use_container_width=True)
    with c2:
        row_t = X_test_t[i:i+1]
        contrib = core.local_contributions(core.shap_values_pos(get_expl(art), row_t), feat_names).head(10).iloc[::-1]
        bar = go.Figure(go.Bar(x=contrib["shap"], y=[pretty(f) for f in contrib["feature"]], orientation="h",
                               marker_color=[POS if v > 0 else NEG for v in contrib["shap"]], marker_line_width=0))
        bar.add_vline(x=0, line_color=MUTED, line_width=1)
        st.plotly_chart(_style(bar, 380, "Why — top drivers of this prediction"), use_container_width=True)
        st.caption("Red pushes toward fraud; blue toward genuine (SHAP contribution).")

# ---------------------------------------------------------------- Performance
with tab_perf:
    st.subheader(f"Performance @ threshold {threshold:.2f}")
    s = m["scores"]
    cols = st.columns(6)
    for col, (label, val) in zip(cols, [("Accuracy", s["Accuracy"]), ("Precision", s["Precision"]),
                                        ("Recall", s["Recall"]), ("F1", s["F1"]),
                                        ("ROC-AUC", s["ROC_AUC"]), ("PR-AUC", s["PR_AUC"])]):
        col.metric(label, f"{val:.3f}")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        cm = m["confusion"]
        hm = go.Figure(go.Heatmap(z=cm, x=["Pred: genuine", "Pred: fraud"], y=["True: genuine", "True: fraud"],
                                  colorscale=BLUE_SEQ, showscale=False, text=cm, texttemplate="%{text}",
                                  textfont={"size": 18}))
        st.plotly_chart(_style(hm, 340, "Confusion matrix"), use_container_width=True)
    with c2:
        fpr, tpr = m["roc"]
        roc = go.Figure()
        roc.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines", line=dict(color=BLUE, width=2), name="Model"))
        roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                 line=dict(color=MUTED, width=1, dash="dash"), name="Random"))
        roc.update_xaxes(title="False positive rate"); roc.update_yaxes(title="True positive rate")
        st.plotly_chart(_style(roc, 340, f"ROC curve · AUC {s['ROC_AUC']:.3f}"), use_container_width=True)
    rec, prec = m["pr"]
    pr = go.Figure()
    pr.add_trace(go.Scatter(x=rec, y=prec, mode="lines", line=dict(color=AQUA, width=2), name="Model"))
    pr.add_hline(y=m["baseline"], line=dict(color=MUTED, width=1, dash="dash"),
                 annotation_text=f"Prevalence {m['baseline']:.2%}")
    pr.update_xaxes(title="Recall"); pr.update_yaxes(title="Precision")
    st.plotly_chart(_style(pr, 340, f"Precision-Recall curve · AP {s['PR_AUC']:.3f}"), use_container_width=True)

# ---------------------------------------------------------------- Explainability
with tab_xai:
    st.subheader("What drives the model, globally")
    st.caption("Mean absolute SHAP value per feature over a sample of the test set.")
    imp = art.get("global_importance")
    if imp is None:
        imp = global_shap(get_expl(art), X_test_t[:120], feat_names)
    top = imp.head(15).iloc[::-1]
    bar = go.Figure(go.Bar(x=top["importance"], y=[pretty(f) for f in top["feature"]],
                           orientation="h", marker_color=BLUE, marker_line_width=0))
    st.plotly_chart(_style(bar, 480, "Global feature importance (mean |SHAP|)"), use_container_width=True)

# ---------------------------------------------------------------- Ops
with tab_ops:
    st.subheader("Operational health")
    st.caption("Live inference latency, throughput, and resource footprint.")
    c = st.columns(4)
    c[0].metric("p50 latency", f"{lat['p50']:.2f} ms")
    c[1].metric("p95 latency", f"{lat['p95']:.2f} ms")
    c[2].metric("p99 latency", f"{lat['p99']:.2f} ms")
    c[3].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")
    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        hist = go.Figure(go.Histogram(x=lat["latencies_ms"], nbinsx=40, marker_color=BLUE, marker_line_width=0))
        for q, clr in [("p50", STATUS["good"]), ("p95", YELLOW), ("p99", STATUS["critical"])]:
            hist.add_vline(x=lat[q], line=dict(color=clr, width=2, dash="dash"), annotation_text=q)
        hist.update_xaxes(title="Single-row inference latency (ms)"); hist.update_yaxes(title="Count")
        st.plotly_chart(_style(hist, 360, "Latency distribution (200 requests)"), use_container_width=True)
    with c2:
        r = st.columns(2)
        r[0].metric("Process memory", f"{res['process_mem_mb']:.0f} MB")
        r[1].metric("System memory", f"{res['system_mem_pct']:.0f} %")
        r[0].metric("CPU load", f"{res['cpu_pct']:.0f} %")
        r[1].metric("CPU cores", f"{res['n_cores']}")

# ---------------------------------------------------------------- Drift
with tab_drift:
    st.subheader("Data drift — Population Stability Index")
    st.caption("Serving data vs. training distribution. PSI < 0.1 stable · 0.1–0.25 watch · > 0.25 drifted.")
    ref, cur = art["X_ref_eng"], X_eng.copy()
    cols = ["V14", "V17", "V12", "log_amount"]
    shift_col = st.selectbox("Simulate a distribution shift on", ["(none)"] + cols)
    if shift_col != "(none)":
        pct = st.slider("Shift the serving distribution by", -50, 100, 30, 5, format="%d%%")
        cur[shift_col] = cur[shift_col] + (pct / 100.0) * cur[shift_col].std()
        st.caption(f"Injected a {pct:+d}% (of σ) shift on **{shift_col}**.")
    rep = core.drift_report(ref, cur, cols)
    st.dataframe(rep, use_container_width=True, hide_index=True)
    bar = go.Figure(go.Bar(x=rep["feature"], y=rep["PSI"], marker_line_width=0,
                           marker_color=[STATUS["good"] if v < 0.1 else STATUS["warning"] if v < 0.25
                                         else STATUS["critical"] for v in rep["PSI"]]))
    bar.add_hline(y=0.1, line=dict(color=STATUS["warning"], width=1, dash="dash"), annotation_text="watch")
    bar.add_hline(y=0.25, line=dict(color=STATUS["critical"], width=1, dash="dash"), annotation_text="drift")
    bar.update_yaxes(title="PSI")
    st.plotly_chart(_style(bar, 340, "PSI by feature"), use_container_width=True)
