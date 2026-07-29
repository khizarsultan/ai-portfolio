"""Khizar Sultan — SMS Spam (malicious/benign) Detection dashboard."""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
import ui

st.set_page_config(page_title="Khizar Sultan · SMS Spam Detection", layout="wide")
ui.inject(brand_line="SMS Spam Detection — ML Platform")

BLUE, INK, MUTED, SURFACE = ui.BRAND, ui.INK, ui.MUTED, ui.SURFACE
STATUS, POS, NEG, BLUE_SEQ = {"good": ui.GOOD, "critical": ui.CRIT, "warning": ui.WARN}, ui.POS, ui.NEG, ui.BLUE_SEQ
EX = "Congratulations! You've WON a FREE $1000 gift card. Click http://bit.ly/claim now to claim."


def _style(fig, h=360, title=None):
    return ui.style_fig(fig, h=h, title=title)


@st.cache_resource(show_spinner="Loading model…")
def load():
    return core.load_artifact()


@st.cache_data(show_spinner=False)
def perf(_art, threshold):
    return core.performance_metrics(_art, _art["X_test_text"], _art["y_test"], threshold)


@st.cache_data(show_spinner=False)
def bench(_art):
    return core.benchmark_latency(_art, list(_art["X_test_text"]))


art = load()
st.title("SMS Spam — Malicious vs Benign Detection")
st.caption(f"**{art['model_name']}** · {len(art['y_test']):,} test messages — classify, explain, and watch ops health.")
ctl = st.columns([1.4, 2.6])
with ctl[0]:
    threshold = st.slider("Decision threshold", 0.05, 0.95, float(round(art["threshold"], 2)), 0.01,
                          help="Probability cut-off for flagging a message as spam/malicious.")

m, lat, res = perf(art, threshold), bench(art), core.resource_usage()

k = st.columns(6)
k[0].metric("ROC-AUC", f"{m['scores']['ROC_AUC']:.3f}")
k[1].metric("PR-AUC", f"{m['scores']['PR_AUC']:.3f}")
k[2].metric("Recall", f"{m['scores']['Recall']:.1%}", help="Share of spam caught.")
k[3].metric("Precision", f"{m['scores']['Precision']:.1%}")
k[4].metric("p95 latency", f"{lat['p95']:.1f} ms")
k[5].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")

t_pred, t_perf, t_xai, t_ops, t_drift = st.tabs(
    ["Classify & Explain", "Performance", "Explainability", "System & Ops", "Data Drift"])

# ---- Classify & Explain
with t_pred:
    st.subheader("Classify a message and see why")
    text = st.text_area("SMS text", value=EX, height=90)
    if text.strip():
        p = float(core.proba_text(art, [text])[0]); flag = p >= threshold
        c1, c2 = st.columns([1, 1.4], gap="large")
        with c1:
            g = go.Figure(go.Indicator(mode="gauge+number", value=p * 100, number={"suffix": "%", "font": {"size": 40}},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": STATUS["critical"] if flag else STATUS["good"]},
                       "threshold": {"line": {"color": INK, "width": 3}, "value": threshold * 100},
                       "steps": [{"range": [0, threshold * 100], "color": "#eafaea"},
                                 {"range": [threshold * 100, 100], "color": "#fdeaea"}]}))
            st.plotly_chart(_style(g, 240, "Spam probability"), use_container_width=True)
            (st.error if flag else st.success)(
                f"**{'SPAM / malicious' if flag else 'Benign (ham)'}** — {p:.1%}")
        with c2:
            ct = core.explain_text(art, text).iloc[::-1]
            bar = go.Figure(go.Bar(x=ct["contribution"], y=ct["token"], orientation="h",
                                   marker_color=[POS if v > 0 else NEG for v in ct["contribution"]], marker_line_width=0))
            bar.add_vline(x=0, line_color=MUTED, line_width=1)
            st.plotly_chart(_style(bar, 340, "Why — top words driving this decision"), use_container_width=True)
            st.caption("Red words push toward spam; blue words push toward benign.")
    else:
        st.info("Type or paste a message to classify it.")

# ---- Performance
with t_perf:
    s = m["scores"]; cols = st.columns(6)
    for col, (lb, v) in zip(cols, [("Accuracy", s["Accuracy"]), ("Precision", s["Precision"]), ("Recall", s["Recall"]),
                                   ("F1", s["F1"]), ("ROC-AUC", s["ROC_AUC"]), ("PR-AUC", s["PR_AUC"])]):
        col.metric(lb, f"{v:.3f}")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        cm = m["confusion"]
        hm = go.Figure(go.Heatmap(z=cm, x=["Pred: ham", "Pred: spam"], y=["True: ham", "True: spam"],
                                  colorscale=BLUE_SEQ, showscale=False, text=cm, texttemplate="%{text}", textfont={"size": 18}))
        st.plotly_chart(_style(hm, 340, "Confusion matrix"), use_container_width=True)
    with c2:
        fpr, tpr = m["roc"]
        roc = go.Figure()
        roc.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines", line=dict(color=BLUE, width=2), name="Model"))
        roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=MUTED, width=1, dash="dash"), name="Random"))
        roc.update_xaxes(title="False positive rate"); roc.update_yaxes(title="True positive rate")
        st.plotly_chart(_style(roc, 340, f"ROC curve · AUC {s['ROC_AUC']:.3f}"), use_container_width=True)
    rec, prec = m["pr"]
    pr = go.Figure(go.Scatter(x=rec, y=prec, mode="lines", line=dict(color=ui.BRAND_DEEP, width=2)))
    pr.add_hline(y=m["baseline"], line=dict(color=MUTED, width=1, dash="dash"), annotation_text=f"Prevalence {m['baseline']:.1%}")
    pr.update_xaxes(title="Recall"); pr.update_yaxes(title="Precision")
    st.plotly_chart(_style(pr, 340, f"Precision-Recall curve · AP {s['PR_AUC']:.3f}"), use_container_width=True)

# ---- Explainability
with t_xai:
    st.subheader("What signals spam, globally")
    st.caption("Words with the largest positive weight toward the spam class (model coefficients).")
    g = core.global_tokens(art, 15).iloc[::-1]
    bar = go.Figure(go.Bar(x=g["weight"], y=g["token"], orientation="h", marker_color=BLUE, marker_line_width=0))
    st.plotly_chart(_style(bar, 480, "Top spam-indicative words"), use_container_width=True)

# ---- System & Ops
with t_ops:
    st.subheader("Operational health")
    c = st.columns(4)
    c[0].metric("p50 latency", f"{lat['p50']:.2f} ms"); c[1].metric("p95 latency", f"{lat['p95']:.2f} ms")
    c[2].metric("p99 latency", f"{lat['p99']:.2f} ms"); c[3].metric("Throughput", f"{lat['throughput_rps']:,.0f} rps")
    c1, c2 = st.columns([1.4, 1], gap="large")
    with c1:
        h = go.Figure(go.Histogram(x=lat["latencies_ms"], nbinsx=40, marker_color=BLUE, marker_line_width=0))
        for q, clr in [("p50", STATUS["good"]), ("p95", STATUS["warning"]), ("p99", STATUS["critical"])]:
            h.add_vline(x=lat[q], line=dict(color=clr, width=2, dash="dash"), annotation_text=q)
        h.update_xaxes(title="Single-message latency (ms)"); h.update_yaxes(title="Count")
        st.plotly_chart(_style(h, 360, "Latency distribution"), use_container_width=True)
    with c2:
        r = st.columns(2)
        r[0].metric("Process memory", f"{res['process_mem_mb']:.0f} MB"); r[1].metric("System memory", f"{res['system_mem_pct']:.0f} %")
        r[0].metric("CPU load", f"{res['cpu_pct']:.0f} %"); r[1].metric("CPU cores", f"{res['n_cores']}")

# ---- Data Drift
with t_drift:
    st.subheader("Data drift — Population Stability Index")
    st.caption("Serving messages vs. training distribution (text-shape features).")
    ref = core.text_features(art["X_ref_text"]); cur = core.text_features(art["X_test_text"]).copy()
    cols = ["length", "n_digits", "n_words", "n_upper"]
    sc = st.selectbox("Simulate a distribution shift on", ["(none)"] + cols)
    if sc != "(none)":
        pct = st.slider("Shift by", -50, 100, 30, 5, format="%d%%")
        cur[sc] = cur[sc] + (pct / 100.0) * cur[sc].std()
    rep = core.drift_report(ref, cur, cols)
    st.dataframe(rep, use_container_width=True, hide_index=True)
    bar = go.Figure(go.Bar(x=rep["feature"], y=rep["PSI"], marker_line_width=0,
                           marker_color=[STATUS["good"] if v < 0.1 else STATUS["warning"] if v < 0.25 else STATUS["critical"] for v in rep["PSI"]]))
    bar.add_hline(y=0.1, line=dict(color=STATUS["warning"], dash="dash"), annotation_text="watch")
    bar.add_hline(y=0.25, line=dict(color=STATUS["critical"], dash="dash"), annotation_text="drift")
    bar.update_yaxes(title="PSI")
    st.plotly_chart(_style(bar, 320), use_container_width=True)
