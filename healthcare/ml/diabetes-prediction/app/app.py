"""Khizar Sultan — Healthcare ML + MLOps, one unified dashboard.

Three sections shown as a navigation bar across the TOP of the page:
  • Executive Summary — plain-language, business-impact view for stakeholders
  • Model Dashboard    — input → prediction → explainability → performance → ops → drift
  • MLOps Pipeline     — registry, drift-triggered retraining, champion vs challenger, approval

Run:  streamlit run app.py
"""
import streamlit as st
import ui

st.set_page_config(page_title="Khizar Sultan · Healthcare ML + MLOps", layout="wide")

PAGES = [
    st.Page("views/executive_view.py", title="Executive Summary"),
    st.Page("views/model_view.py", title="Model Dashboard", default=True),
    st.Page("views/mlops_view.py", title="MLOps Pipeline"),
]

current = st.navigation(PAGES, position="hidden")   # hide sidebar nav; we render our own on top

ui.inject(brand_line="Diabetes Risk — ML & MLOps Platform")
ui.topnav(PAGES, current)
st.divider()

current.run()
