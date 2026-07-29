"""Executive Summary — a CONFIGURABLE, plain-language view for business stakeholders.

The "Customize view" panel (sidebar) lets each stakeholder choose the time basis, the
cost assumptions, which sections to show, and exactly which business KPIs to display —
so they see only the information they care about. All technical terms live in tooltips.
"""
from __future__ import annotations
import os
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
import ui

GREEN, AMBER, RED = ui.GOOD, ui.WARN, ui.CRIT
BLUE, INK, SURFACE = ui.BRAND, ui.INK, ui.SURFACE

MLOPS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mlops"))
sys.path.insert(0, MLOPS)


@st.cache_resource(show_spinner="Loading model…")
def load():
    return core.load_artifact(), core.get_data()


@st.cache_data(show_spinner=False)
def scored(_art, _data):
    m = core.performance_metrics(_art["model"], _data["X_test_t"], _data["y_test"], _art["threshold"])
    lat = core.benchmark_latency(_art["model"], _data["X_test_t"], n=100)
    return m, lat


def model_status():
    try:
        from steps import registry, evaluate  # noqa
        prod = registry.version_by_alias("production")
        pend = evaluate.load_pending()
        return (f"v{prod.version}" if prod else "—"), bool(pend and pend.get("gate_passed"))
    except Exception:
        return None, False


art, data = load()
m, lat = scored(art, data)
cm = m["confusion"]
tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])
total = tn + fp + fn + tp
recall, precision, roc = m["scores"]["Recall"], m["scores"]["Precision"], m["scores"]["ROC_AUC"]
r_tp, r_fp, r_fn = tp / total, fp / total, fn / total
prod_v, has_pending = model_status()

# =====================================================================
# Customize view (sidebar)
# =====================================================================
SECTIONS = ["Reliability verdict", "At a glance", "Outcomes per 1,000",
            "Business impact & KPIs", "Population stability"]
KPI_ORDER = ["Net value", "Cases caught", "False-alarm cost", "Value per patient screened",
             "Return per $1 of false alarms", "Patients per case caught", "Missed-case exposure",
             "Cases missed", "Detection rate", "Alert precision"]
DEFAULT_KPIS = ["Net value", "Cases caught", "False-alarm cost", "Value per patient screened",
                "Patients per case caught", "Detection rate", "Alert precision", "Missed-case exposure"]

st.title("Diabetes Risk Model — Business Summary")
st.caption("A plain-language view — adjust the controls below and the numbers update live.")
with st.expander("Customize view — assumptions are illustrative", expanded=True):
    cc = st.columns(4, vertical_alignment="bottom")
    basis = cc[0].radio("Time basis", ["Monthly", "Annual"], horizontal=True)
    value_case = cc[1].number_input("Value of catching one case early ($)", 0, 1_000_000, 1200, 50)
    cost_alarm = cc[2].number_input("Cost of one false alarm ($)", 0, 1_000_000, 80, 10)
    volume = cc[3].number_input("Patients screened per month", 100, 5_000_000, 10_000, 500)
sections = SECTIONS
kpis = DEFAULT_KPIS

mult = 12 if basis == "Annual" else 1
per = "year" if basis == "Annual" else "month"
caught = r_tp * volume * mult
alarms = r_fp * volume * mult
missed = r_fn * volume * mult
gross = caught * value_case
alarm_cost = alarms * cost_alarm
net = gross - alarm_cost
per_patient = net / (volume * mult) if volume else 0
ratio = gross / alarm_cost if alarm_cost else None
nns = (volume * mult) / caught if caught else 0
missed_exposure = missed * value_case

KPIS = {
    "Net value": (f"Net value / {per}", f"${net:,.0f}", "Net benefit at current settings."),
    "Cases caught": (f"Cases caught / {per}", f"{caught:,.0f}", "True cases flagged for follow-up."),
    "False-alarm cost": (f"False-alarm cost / {per}", f"${alarm_cost:,.0f}", "Cost of following up healthy patients."),
    "Missed-case exposure": (f"Missed-case exposure / {per}", f"${missed_exposure:,.0f}", "Value not captured from missed cases."),
    "Cases missed": (f"Cases missed / {per}", f"{missed:,.0f}", "True cases the model does not flag."),
    "Value per patient screened": ("Value per patient screened", f"${per_patient:,.2f}", "Net value per screening."),
    "Return per $1 of false alarms": ("Return per $1 of false alarms",
                                      "no false alarms" if ratio is None else f"${ratio:,.0f}",
                                      "Early-detection value for every $1 of false-alarm cost."),
    "Patients per case caught": ("Patients per case caught", f"{nns:,.0f}", "Screenings to catch one true case."),
    "Detection rate": ("Detection rate", f"{recall*100:.0f}%", "Share of true cases caught (recall)."),
    "Alert precision": ("Alert precision", f"{precision*100:.0f}%", "Share of flags that are truly at risk."),
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
    banner = (f"Overall reliability: **{grade}**. The model correctly tells high-risk from "
              f"low-risk patients about **{roc*100:.0f} times out of 100**.")
    (st.success if grade in ("Strong", "Good") else st.warning)(banner)
    if has_pending:
        st.info("A newer model has passed automated checks and is **awaiting your approval** "
                "on the MLOps Pipeline page.")

if "At a glance" in sections:
    st.subheader("At a glance")
    k = st.columns(4)
    k[0].metric("Catches true cases", f"{recall*100:.0f} of 100",
                help="Of patients who truly have diabetes, how many the model flags. (recall)")
    k[1].metric("Alerts that are correct", f"{precision*100:.0f}%",
                help="When the model flags a patient, how often it is right. (precision)")
    k[2].metric("Speed per patient", "Instant",
                help=f"~{lat['p95']:.0f} ms per patient — effectively real-time. (p95 latency)")
    k[3].metric("Model in use", prod_v or "live",
                help="The version currently serving predictions, governed by the MLOps pipeline.")

if "Outcomes per 1,000" in sections:
    st.subheader("What happens for every 1,000 patients screened")
    st.caption("Based on the model's results on held-out patients, at its current alert setting.")
    scale = 1000 / total
    c1000, m1000, a1000, cl1000 = tp * scale, fn * scale, fp * scale, tn * scale
    o = st.columns(4)
    o[0].metric("At-risk correctly caught", f"{c1000:.0f}", help="True cases flagged for follow-up.")
    o[1].metric("At-risk missed", f"{m1000:.0f}", help="True cases not flagged — the key risk.")
    o[2].metric("False alarms", f"{a1000:.0f}", help="Healthy patients flagged who turn out fine.")
    o[3].metric("Correctly cleared", f"{cl1000:.0f}", help="Healthy patients correctly left alone.")
    fig = go.Figure(go.Bar(x=["Caught", "Missed"], y=[c1000, m1000],
                           marker_color=[GREEN, RED],
                           text=[f"{c1000:.0f}", f"{m1000:.0f}"], textposition="auto"))
    ui.style_fig(fig, h=280, title="Of the true at-risk patients: caught vs missed")
    fig.update_yaxes(title="patients per 1,000")
    st.plotly_chart(fig, use_container_width=True)

if "Business impact & KPIs" in sections:
    st.subheader(f"Estimated business impact ({per}ly)")
    st.caption(f"Value from early detection ${gross:,.0f} − false-alarm cost ${alarm_cost:,.0f} "
               f"= **${net:,.0f} per {per}**. *Illustrative — adjust assumptions in the sidebar.*")
    if kpis:
        kpi_grid(kpis)
    else:
        st.caption("No KPIs selected — pick some under **Business KPIs to show** in the sidebar.")

if "Population stability" in sections:
    st.subheader("Can we still trust it?")
    try:
        worst = core.drift_report(data["X_train"], data["X_test"])["status"].tolist()
        if "DRIFT" in worst:
            st.error("The incoming patient population has **shifted** from what the model learned — "
                     "a model refresh is recommended. (data drift)")
        elif "WARNING" in worst:
            st.warning("The patient population is **drifting slightly** — worth monitoring. (data drift)")
        else:
            st.success("The incoming patient population looks **like the data the model learned from**, "
                       "so its results remain trustworthy. (data drift)")
    except Exception:
        st.info("Population-stability check unavailable.")
    st.caption("Model updates are proposed automatically when data shifts, checked against the current "
               "model, and go live only after a human approves them — see the MLOps Pipeline page.")
