"""Khizar Sultan — Malicious URL Detection: ML + MLOps, one unified dashboard."""
import streamlit as st
import ui

st.set_page_config(page_title="Khizar Sultan · URL Threat ML + MLOps", layout="wide")

PAGES = [
    st.Page("views/executive_view.py", title="Executive Summary"),
    st.Page("views/model_view.py", title="Model Dashboard", default=True),
    st.Page("views/mlops_view.py", title="MLOps Pipeline"),
]
current = st.navigation(PAGES, position="hidden")
ui.inject(brand_line="Malicious URL Detection — ML & MLOps Platform")
ui.topnav(PAGES, current)
st.divider()
current.run()
