"""Executive Summary — configurable, plain-language view for business stakeholders (fraud)."""
from __future__ import annotations
import os
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
import ui

GREEN, AMBER, RED, BLUE = ui.GOOD, ui.WARN, ui.CRIT, ui.BRAND
MLOPS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mlops"))
sys.path.insert(0, MLOPS)


@st.cache_resource(show_spinner="Loading model…")
def load():
    art = core.load_artifact()
    return art, core.transform(art, art["X_test_eng"]), art["y_test"]


@st.cache_data(show_spinner=False)
def scored(_art, _Xt, y, threshold):
    return core.performance_metrics(_art["model"], _Xt, y, threshold), core.benchmark_latency(_art["model"], _Xt, n=100)


def model_status():
    try:
        from steps import registry, evaluate  # noqa
        prod = registry.version_by_alias("production")
        return (f"v{prod.version}" if prod else "—"), bool(evaluate.load_pending())
    except Exception:
        return None, False


art, X_test_t, y_test = load()
threshold = float(art["threshold"])
m, lat = scored(art, X_test_t, y_test, threshold)
cm = m["confusion"]
tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])
total = tn + fp + fn + tp
recall, precision, roc = m["scores"]["Recall"], m["scores"]["Precision"], m["scores"]["ROC_AUC"]
r_tp, r_fp, r_fn = tp / total, fp / total, fn / total
prod_v, has_pending = model_status()

SECTIONS = ["Reliability verdict", "At a glance", "Outcomes per 10,000",
            "Business impact & KPIs", "Population stability"]
KPI_ORDER = ["Net value", "Fraud caught", "False-alarm cost", "Value per transaction",
             "Return per $1 of false alarms", "Transactions per fraud caught",
             "Missed-fraud exposure", "Fraud missed", "Catch rate", "Alert precision"]
DEFAULT_KPIS = ["Net value", "Fraud caught", "False-alarm cost", "Value per transaction",
                "Transactions per fraud caught", "Catch rate", "Alert precision", "Missed-fraud exposure"]

st.title("Credit-Card Fraud Model — Business Summary")
st.caption("A plain-language view — adjust the controls below and the numbers update live.")
with st.expander("Customize view — assumptions are illustrative", expanded=True):
    cc = st.columns(4, vertical_alignment="bottom")
    basis = cc[0].radio("Time basis", ["Monthly", "Annual"], horizontal=True)
    value_fraud = cc[1].number_input("Value of catching one fraud ($)", 0, 1_000_000, 200, 25)
    cost_alarm = cc[2].number_input("Cost of one false alarm ($)", 0, 1_000_000, 5, 1)
    volume = cc[3].number_input("Transactions per month", 1000, 500_000_000, 1_000_000, 10_000)
sections = SECTIONS
kpis = DEFAULT_KPIS

mult = 12 if basis == "Annual" else 1
per = "year" if basis == "Annual" else "month"
caught = r_tp * volume * mult
alarms = r_fp * volume * mult
missed = r_fn * volume * mult
gross = caught * value_fraud
alarm_cost = alarms * cost_alarm
net = gross - alarm_cost
per_txn = net / (volume * mult) if volume else 0
ratio = gross / alarm_cost if alarm_cost else None
tpf = (volume * mult) / caught if caught else 0
missed_exposure = missed * value_fraud

KPIS = {
    "Net value": (f"Net value / {per}", f"${net:,.0f}", "Net benefit at current settings."),
    "Fraud caught": (f"Fraud caught / {per}", f"{caught:,.0f}", "Fraudulent transactions flagged."),
    "False-alarm cost": (f"False-alarm cost / {per}", f"${alarm_cost:,.0f}", "Cost of reviewing legit transactions flagged."),
    "Missed-fraud exposure": (f"Missed-fraud exposure / {per}", f"${missed_exposure:,.0f}", "Value lost to fraud the model misses."),
    "Fraud missed": (f"Fraud missed / {per}", f"{missed:,.0f}", "Fraud the model does not flag."),
    "Value per transaction": ("Value per transaction", f"${per_txn:,.4f}", "Net value per transaction screened."),
    "Return per $1 of false alarms": ("Return per $1 of false alarms",
                                      "no false alarms" if ratio is None else f"${ratio:,.0f}",
                                      "Fraud value saved per $1 of false-alarm cost."),
    "Transactions per fraud caught": ("Transactions per fraud caught", f"{tpf:,.0f}", "Transactions screened per fraud caught."),
    "Catch rate": ("Catch rate", f"{recall*100:.0f}%", "Share of fraud the model catches (recall)."),
    "Alert precision": ("Alert precision", f"{precision*100:.0f}%", "Share of flags that are truly fraud."),
}


def kpi_grid(keys, ncol=4):
    keys = [k for k in KPI_ORDER if k in keys]
    for i in range(0, len(keys), ncol):
        cols = st.columns(ncol)
        for col, k in zip(cols, keys[i:i + ncol]):
            label, val, hlp = KPIS[k]
            col.metric(label, val, help=hlp)


if "Reliability verdict" in sections:
    grade = "Strong" if roc >= 0.9 else "Good" if roc >= 0.8 else "Fair" if roc >= 0.7 else "Needs work"
    (st.success if grade in ("Strong", "Good") else st.warning)(
        f"Overall reliability: **{grade}**. The model separates fraud from genuine transactions "
        f"about **{roc*100:.0f} times out of 100**.")
    if has_pending:
        st.info("A newer model is **awaiting your approval** on the MLOps Pipeline page.")

if "At a glance" in sections:
    st.subheader("At a glance")
    k = st.columns(4)
    k[0].metric("Catches fraud", f"{recall*100:.0f} of 100", help="Of truly-fraudulent transactions, how many are flagged. (recall)")
    k[1].metric("Alerts that are correct", f"{precision*100:.0f}%", help="When the model flags a transaction, how often it is right. (precision)")
    k[2].metric("Speed per transaction", "Instant", help=f"~{lat['p95']:.0f} ms — real-time. (p95 latency)")
    k[3].metric("Model in use", prod_v or "live", help="Version currently serving, governed by the MLOps pipeline.")

if "Outcomes per 10,000" in sections:
    st.subheader("What happens for every 10,000 transactions")
    st.caption("Based on held-out results at the current alert setting.")
    sc = 10000 / total
    o = st.columns(4)
    o[0].metric("Fraud correctly caught", f"{tp*sc:.0f}")
    o[1].metric("Fraud missed", f"{fn*sc:.0f}")
    o[2].metric("False alarms", f"{fp*sc:.0f}")
    o[3].metric("Correctly cleared", f"{tn*sc:,.0f}")
    fig = go.Figure(go.Bar(x=["Caught", "Missed"], y=[tp*sc, fn*sc], marker_color=[GREEN, RED],
                           text=[f"{tp*sc:.0f}", f"{fn*sc:.0f}"], textposition="auto"))
    ui.style_fig(fig, h=280, title="Of the true fraud: caught vs missed")
    fig.update_yaxes(title="per 10,000 transactions")
    st.plotly_chart(fig, use_container_width=True)

if "Business impact & KPIs" in sections:
    st.subheader(f"Estimated business impact ({per}ly)")
    st.caption(f"Fraud value saved ${gross:,.0f} − false-alarm cost ${alarm_cost:,.0f} "
               f"= **${net:,.0f} per {per}**. *Illustrative — adjust assumptions in the sidebar.*")
    kpi_grid(kpis) if kpis else st.caption("No KPIs selected.")

if "Population stability" in sections:
    st.subheader("Can we still trust it?")
    try:
        worst = core.drift_report(art["X_ref_eng"], art["X_test_eng"], ["V14", "V17", "V12", "log_amount"])["status"].tolist()
        if "DRIFT" in worst:
            st.error("Incoming transactions have **shifted** from training — a model refresh is recommended. (data drift)")
        elif "WARNING" in worst:
            st.warning("Transactions are **drifting slightly** — worth monitoring. (data drift)")
        else:
            st.success("Incoming transactions look **like the training data**, so results remain trustworthy. (data drift)")
    except Exception:
        st.info("Population-stability check unavailable.")
    st.caption("Updates are proposed automatically on drift, checked vs the current model, and go live "
               "only after a human approves them — see the MLOps Pipeline page.")
