"""Executive Summary — configurable, plain-language view for stakeholders (URL threats)."""
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
    return art, core.transform(art, art["X_test_eng"]), art["y_test"], art["classes"]


@st.cache_data(show_spinner=False)
def scored(_art, _Xt, y, classes):
    return core.performance_metrics(_art["model"], _Xt, y, classes), core.benchmark_latency(_art["model"], _Xt, n=100)


def model_status():
    try:
        from steps import registry, evaluate  # noqa
        prod = registry.version_by_alias("production")
        return (f"v{prod.version}" if prod else "—"), bool(evaluate.load_pending())
    except Exception:
        return None, False


art, X_test_t, y_test, classes = load()
m, lat = scored(art, X_test_t, y_test, classes)
pc = m["per_class"]
cc = np.asarray(m["confusion_counts"])          # rows=true, cols=pred (labels=classes)
bi = classes.index("benign")
mal = [i for i in range(len(classes)) if i != bi]
total = int(cc.sum())
true_mal = int(cc[mal, :].sum())
caught = int(cc[np.ix_(mal, mal)].sum())        # true malicious flagged as some threat
missed = int(cc[mal, bi].sum())                 # true malicious called benign
false_block = int(cc[bi, mal].sum())            # true benign flagged as threat
catch_rate = caught / true_mal if true_mal else 0
alert_prec = caught / (caught + false_block) if (caught + false_block) else 0
prod_v, has_pending = model_status()

SECTIONS = ["Reliability verdict", "At a glance", "Threat outcomes per 10,000",
            "Business impact & KPIs", "Population stability"]
KPI_ORDER = ["Net value", "Threats blocked", "False-block cost", "Value per URL",
             "Return per $1 of false blocks", "URLs per threat caught",
             "Missed-threat exposure", "Threats missed", "Threat catch rate", "Alert precision"]
DEFAULT_KPIS = ["Net value", "Threats blocked", "False-block cost", "Value per URL",
                "URLs per threat caught", "Threat catch rate", "Alert precision", "Missed-threat exposure"]

st.title("Malicious URL Detection — Business Summary")
st.caption("A plain-language view — adjust the controls below and the numbers update live.")
with st.expander("Customize view — assumptions are illustrative", expanded=True):
    fc = st.columns(4, vertical_alignment="bottom")
    basis = fc[0].radio("Time basis", ["Monthly", "Annual"], horizontal=True)
    value_threat = fc[1].number_input("Value of blocking one malicious URL ($)", 0, 1_000_000, 50, 5)
    cost_block = fc[2].number_input("Cost of one false block ($)", 0, 1_000_000, 3, 1)
    volume = fc[3].number_input("URLs scanned per month", 1000, 500_000_000, 1_000_000, 10_000)
sections = SECTIONS
kpis = DEFAULT_KPIS

mult = 12 if basis == "Annual" else 1
per = "year" if basis == "Annual" else "month"
r_caught, r_missed, r_fb = caught / total, missed / total, false_block / total
n_caught = r_caught * volume * mult
n_missed = r_missed * volume * mult
n_fb = r_fb * volume * mult
gross = n_caught * value_threat
block_cost = n_fb * cost_block
net = gross - block_cost
per_url = net / (volume * mult) if volume else 0
ratio = gross / block_cost if block_cost else None
upt = (volume * mult) / n_caught if n_caught else 0
missed_exposure = n_missed * value_threat

KPIS = {
    "Net value": (f"Net value / {per}", f"${net:,.0f}", "Net benefit at current settings."),
    "Threats blocked": (f"Threats blocked / {per}", f"{n_caught:,.0f}", "Malicious URLs correctly flagged."),
    "False-block cost": (f"False-block cost / {per}", f"${block_cost:,.0f}", "Cost of blocking safe URLs by mistake."),
    "Missed-threat exposure": (f"Missed-threat exposure / {per}", f"${missed_exposure:,.0f}", "Value lost to threats let through."),
    "Threats missed": (f"Threats missed / {per}", f"{n_missed:,.0f}", "Malicious URLs the model lets through."),
    "Value per URL": ("Value per URL scanned", f"${per_url:,.4f}", "Net value per URL scanned."),
    "Return per $1 of false blocks": ("Return per $1 of false blocks",
                                      "no false blocks" if ratio is None else f"${ratio:,.0f}",
                                      "Threat value blocked per $1 of false-block cost."),
    "URLs per threat caught": ("URLs per threat caught", f"{upt:,.0f}", "URLs scanned per threat blocked."),
    "Threat catch rate": ("Threat catch rate", f"{catch_rate*100:.0f}%", "Share of malicious URLs blocked."),
    "Alert precision": ("Alert precision", f"{alert_prec*100:.0f}%", "Share of blocks that are truly malicious."),
}


def kpi_grid(keys, ncol=4):
    keys = [k for k in KPI_ORDER if k in keys]
    for i in range(0, len(keys), ncol):
        cols = st.columns(ncol)
        for col, k in zip(cols, keys[i:i + ncol]):
            label, val, hlp = KPIS[k]
            col.metric(label, val, help=hlp)


if "Reliability verdict" in sections:
    f1 = m["macro_f1"]
    grade = "Strong" if f1 >= 0.9 else "Good" if f1 >= 0.8 else "Fair" if f1 >= 0.7 else "Needs work"
    (st.success if grade in ("Strong", "Good") else st.warning)(
        f"Overall reliability: **{grade}**. Across all four URL types the model scores a "
        f"balanced accuracy (macro-F1) of **{f1:.2f}** out of 1.00.")
    if has_pending:
        st.info("A newer model is **awaiting your approval** on the MLOps Pipeline page.")

if "At a glance" in sections:
    st.subheader("At a glance")
    k = st.columns(4)
    k[0].metric("Blocks real threats", f"{catch_rate*100:.0f} of 100", help="Of truly-malicious URLs, how many are blocked.")
    k[1].metric("Blocks that are correct", f"{alert_prec*100:.0f}%", help="When the model blocks a URL, how often it is truly malicious.")
    k[2].metric("Speed per URL", "Instant", help=f"~{lat['p95']:.0f} ms — real-time. (p95 latency)")
    k[3].metric("Model in use", prod_v or "live", help="Version currently serving, governed by the MLOps pipeline.")

if "Threat outcomes per 10,000" in sections:
    st.subheader("What happens for every 10,000 URLs")
    st.caption("Based on held-out results, combining all malicious types into 'threats'.")
    sc = 10000 / total
    o = st.columns(4)
    o[0].metric("Threats blocked", f"{caught*sc:.0f}")
    o[1].metric("Threats missed", f"{missed*sc:.0f}")
    o[2].metric("Safe URLs false-blocked", f"{false_block*sc:.0f}")
    o[3].metric("Safe URLs allowed", f"{(cc[bi, bi])*sc:,.0f}")
    fig = go.Figure(go.Bar(x=["Blocked", "Missed"], y=[caught*sc, missed*sc], marker_color=[GREEN, RED],
                           text=[f"{caught*sc:.0f}", f"{missed*sc:.0f}"], textposition="auto"))
    ui.style_fig(fig, h=280, title="Of the true threats: blocked vs missed")
    fig.update_yaxes(title="per 10,000 URLs")
    st.plotly_chart(fig, use_container_width=True)

if "Business impact & KPIs" in sections:
    st.subheader(f"Estimated business impact ({per}ly)")
    st.caption(f"Threat value blocked ${gross:,.0f} − false-block cost ${block_cost:,.0f} "
               f"= **${net:,.0f} per {per}**. *Illustrative — adjust assumptions in the sidebar.*")
    kpi_grid(kpis) if kpis else st.caption("No KPIs selected.")

if "Population stability" in sections:
    st.subheader("Can we still trust it?")
    try:
        worst = core.drift_report(art["X_ref_eng"], art["X_test_eng"],
                                  ["url_len", "n_digits", "digit_ratio", "url_entropy"])["status"].tolist()
        if "DRIFT" in worst:
            st.error("Incoming URL traffic has **shifted** from training — a model refresh is recommended. (data drift)")
        elif "WARNING" in worst:
            st.warning("URL traffic is **drifting slightly** — worth monitoring. (data drift)")
        else:
            st.success("Incoming URL traffic looks **like the training data**, so results remain trustworthy. (data drift)")
    except Exception:
        st.info("Population-stability check unavailable.")
    st.caption("Updates are proposed automatically on drift, checked vs the current model, and go live "
               "only after a human approves them — see the MLOps Pipeline page.")
