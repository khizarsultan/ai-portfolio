"""Khizar Sultan — Malicious URL Detection MLOps dashboard.

Paste a URL → get benign/defacement/malware/phishing probabilities and a SHAP
explanation of the decision. Five views: predict, evaluate, explain, operate, monitor.
Computation lives in core.py; this file is presentation only.
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
# security-semantic class colors (benign = safe green, malware = red, phishing = orange)
CLASS_COLORS = {"benign": "#1baf7a", "defacement": "#eda100", "malware": "#d03b3b", "phishing": "#eb6834"}

def _style(fig, h=360, title=None):
    return ui.style_fig(fig, h=h, title=title)


def pretty(name: str) -> str:
    for p in ("log__", "num__", "cat__", "bin__"):
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
def perf(_model, _Xt, y, classes):
    return core.performance_metrics(_model, _Xt, y, classes)


@st.cache_data(show_spinner="Benchmarking…")
def bench(_model, _Xt):
    return core.benchmark_latency(_model, _Xt, n=200)


@st.cache_data(show_spinner="Computing global explanations…")
def global_shap(_expl, _Xs, feature_names):
    return core.global_importance_mc(_expl, _Xs, feature_names)


art, X_test_t = load()
model, feat_names, classes = art["model"], art["feature_names"], art["classes"]
y_test = art["y_test"]

m = perf(model, X_test_t, y_test, classes)
lat = art.get("latency") or bench(model, X_test_t)
res = core.resource_usage()
pc = m["per_class"]

st.title("Malicious URL Detection — ML & MLOps Dashboard")
st.caption(f"**{art['model_name']}** · {len(y_test):,} test URLs · 4 classes — per-URL explanations and live ops health.")

k = st.columns(6)
k[0].metric("Macro-F1", f"{m['macro_f1']:.3f}")
k[1].metric("Macro-recall", f"{m['macro_recall']:.3f}")
k[2].metric("Malware recall", f"{pc.loc['malware', 'recall']:.1%}", help="Share of malware URLs caught.")
k[3].metric("Phishing recall", f"{pc.loc['phishing', 'recall']:.1%}")
k[4].metric("p95 latency", f"{lat['p95']:.1f} ms")
k[5].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")

tab_pred, tab_perf, tab_xai, tab_ops, tab_drift = st.tabs(
    ["Classify & Explain", "Performance", "Explainability", "System & Ops", "Data Drift"])

# ---------------------------------------------------------------- Predict
with tab_pred:
    st.subheader("Classify a URL and see why")

    def _set(u):
        st.session_state.url = u

    ex = art.get("examples", {})
    if "url" not in st.session_state:
        st.session_state.url = (ex.get("phishing") or ex.get("malware") or [""])[0]
    st.caption("Quick-fill a real example:")
    bcols = st.columns(len(classes))
    for col, c in zip(bcols, classes):
        if ex.get(c):
            col.button(f"{c}", on_click=_set, args=(ex[c][0],), use_container_width=True)
    url = st.text_input("URL", key="url")

    if url.strip():
        row_eng = core.featurize_url(art, url)
        row_t = art["preprocessor"].transform(row_eng)
        proba = model.predict_proba(row_t)[0]
        idx = int(np.argmax(proba))
        label = classes[idx]

        c1, c2 = st.columns([1, 1.4], gap="large")
        with c1:
            safe = label == "benign"
            (st.success if safe else st.error)(
                f"Prediction: **{label.upper()}**  ·  confidence {proba[idx]:.1%}")
            bar = go.Figure(go.Bar(x=proba, y=classes, orientation="h",
                                   marker_color=[CLASS_COLORS[c] for c in classes], marker_line_width=0,
                                   text=[f"{p:.1%}" for p in proba], textposition="auto"))
            bar.update_xaxes(range=[0, 1], title="probability")
            st.plotly_chart(_style(bar, 260, "Class probabilities"), use_container_width=True)
        with c2:
            contrib = core.local_contributions(
                core.shap_values_class(get_expl(art), row_t, idx), feat_names).head(10).iloc[::-1]
            fig = go.Figure(go.Bar(x=contrib["shap"], y=[pretty(f) for f in contrib["feature"]],
                                   orientation="h",
                                   marker_color=[POS if v > 0 else NEG for v in contrib["shap"]],
                                   marker_line_width=0))
            fig.add_vline(x=0, line_color=MUTED, line_width=1)
            st.plotly_chart(_style(fig, 340, f"Why — top drivers toward '{label}'"), use_container_width=True)
            st.caption(f"Red pushes toward **{label}**; blue pushes away (SHAP contribution).")
    else:
        st.info("Enter a URL (or click an example) to classify it with an explanation.")

# ---------------------------------------------------------------- Performance
with tab_perf:
    st.subheader("Performance on the held-out test set")
    c = st.columns(4)
    c[0].metric("Accuracy", f"{m['accuracy']:.3f}", help="Misleading here — 67% of URLs are benign.")
    c[1].metric("Macro-F1", f"{m['macro_f1']:.3f}")
    c[2].metric("Macro-recall", f"{m['macro_recall']:.3f}")
    c[3].metric("Macro ROC-AUC", f"{m['macro_roc_auc']:.3f}")

    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        cm = m["confusion"]
        hm = go.Figure(go.Heatmap(z=cm, x=[f"pred {c}" for c in classes], y=[f"true {c}" for c in classes],
                                  colorscale=BLUE_SEQ, zmin=0, zmax=1, showscale=True,
                                  text=np.round(cm, 2), texttemplate="%{text}", textfont={"size": 12}))
        st.plotly_chart(_style(hm, 380, "Confusion matrix (row-normalized = recall on diagonal)"),
                        use_container_width=True)
    with c2:
        rbar = go.Figure(go.Bar(x=classes, y=pc["recall"], marker_line_width=0,
                                marker_color=[CLASS_COLORS[c] for c in classes],
                                text=[f"{v:.1%}" for v in pc["recall"]], textposition="auto"))
        rbar.update_yaxes(range=[0, 1], title="recall")
        st.plotly_chart(_style(rbar, 380, "Per-class recall (catch-rate)"), use_container_width=True)

    st.markdown("**Per-class metrics**")
    st.dataframe(pc.style.format({"precision": "{:.3f}", "recall": "{:.3f}",
                                  "f1": "{:.3f}", "support": "{:,.0f}"}), use_container_width=True)

# ---------------------------------------------------------------- Explainability
with tab_xai:
    st.subheader("What drives the model, globally")
    st.caption("Mean absolute SHAP value per feature, aggregated across all four classes.")
    imp = art.get("global_importance")
    if imp is None:
        imp = global_shap(get_expl(art), X_test_t[:60], feat_names)
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
    st.caption("Serving URLs vs. training distribution. PSI < 0.1 stable · 0.1–0.25 watch · > 0.25 drifted.")
    ref, cur = art["X_ref_eng"], art["X_test_eng"].copy()
    cols = ["url_len", "n_digits", "digit_ratio", "url_entropy", "n_slash", "host_len"]
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
