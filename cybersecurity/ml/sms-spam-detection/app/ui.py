"""Shared UI theme — design system imported from the Claude Design
"OCR Engine Benchmark" project (fonts, colors, cards, tables, charts).

  Fonts   Space Grotesk (headings) · IBM Plex Sans (body) · IBM Plex Mono (numbers)
  Colors  page #f5f6f8 · brand #2f6bf0 · ink #0f131b · muted #5b6472 · line #e7e9ee
  Cards   white, 1px #e7e9ee, radius 16, layered soft shadow

Call inject() once per page load (from the app entry point). Views import the color
and font constants below so charts match the CSS.
"""
from __future__ import annotations
import streamlit as st

# ---- design tokens (shared with Plotly charts in the views) ----
BRAND = "#2f6bf0"
BRAND_HOVER = "#1f57d6"
BRAND_DEEP = "#1e3a8a"
BRAND_SOFT = "#eaf0fe"
INK = "#0f131b"
INK2 = "#1a1f2b"
MUTED = "#5b6472"
MUTED2 = "#8b93a1"
FAINT = "#a1a8b4"
LINE = "#e7e9ee"
LINE2 = "#eef0f4"
PAGE = "#f5f6f8"
SURFACE = "#ffffff"
NEUTRAL = "#9aa3b2"          # secondary chart series
# semantic status colors for traffic-lights (comprehension)
GOOD, WARN, CRIT = "#12833a", "#c98a00", "#d0453b"
# SHAP diverging: raises risk (red) / lowers risk (brand blue)
POS, NEG = "#d0453b", "#2f6bf0"
# sequential blue heatmap (from the design's oklch ramp)
BLUE_SEQ = [[0.0, "#eef3fe"], [0.5, "#8fb2f6"], [1.0, "#1f57d6"]]

FONT_SANS = "'IBM Plex Sans', -apple-system, sans-serif"
FONT_MONO = "'IBM Plex Mono', monospace"
FONT_HEAD = "'Space Grotesk', sans-serif"

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{
  --brand:#2f6bf0; --brand-hover:#1f57d6; --brand-deep:#1e3a8a; --brand-soft:#eaf0fe; --brand-tint:#f4f8ff;
  --page:#f5f6f8; --surface:#ffffff; --ink:#0f131b; --ink2:#1a1f2b;
  --muted:#5b6472; --muted2:#8b93a1; --faint:#a1a8b4; --line:#e7e9ee; --line2:#eef0f4;
}

/* ---- fonts & canvas ---- */
html, body, .stApp, [data-testid="stAppViewContainer"], [class*="st-"]{
  font-family:'IBM Plex Sans', -apple-system, sans-serif;
}
.stApp, [data-testid="stAppViewContainer"]{ background:var(--page); }
[data-testid="stHeader"]{ background:transparent; }
/* keep Material icon ligatures rendering as glyphs (not raw text like "keyboard_arrow_right") */
[data-testid="stIconMaterial"], [data-testid="stExpanderToggleIcon"],
span.material-icons, span.material-symbols-rounded, span.material-symbols-outlined{
  font-family:'Material Symbols Rounded','Material Symbols Outlined','Material Icons' !important;
}
h1,h2,h3,h4{ font-family:'Space Grotesk', sans-serif !important; color:var(--ink);
  letter-spacing:-.02em; }
h1{ font-weight:700; font-size:2rem; }
h2{ font-weight:600; } h3{ font-weight:600; }
a{ color:var(--brand); text-decoration:none; } a:hover{ color:var(--brand-hover); }
::selection{ background:#d7e2fd; }

.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:1160px; }
hr{ margin:.9rem 0; border:none; border-top:1px solid var(--line); }
#MainMenu, footer{ visibility:hidden; }
[data-testid="stDecoration"], [data-testid="stStatusWidget"]{ display:none; }

/* ---- brand bar ---- */
.appbar{ display:flex; align-items:center; gap:9px; margin:0 0 .6rem 2px; }
.appbar .dot{ width:9px; height:9px; border-radius:50%; background:var(--brand); }
.appbar .txt{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:12px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted); }

/* ---- top navigation buttons ---- */
.stButton>button{ border-radius:11px; font-weight:600; padding:.55rem 1rem;
  border:1px solid var(--line); background:var(--surface); color:var(--ink2); transition:all .12s ease; }
.stButton>button:hover{ border-color:var(--brand); color:var(--brand); }
.stButton>button[kind="primary"]{ background:var(--brand); border-color:var(--brand); color:#fff;
  box-shadow:0 6px 18px rgba(47,107,240,.28); }
.stButton>button[kind="primary"]:hover{ background:var(--brand-hover); color:#fff; }

/* ---- tabs: prominent, pill-like ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"]{ gap:4px; border-bottom:2px solid var(--line); }
[data-testid="stTabs"] button[data-baseweb="tab"]{ font-size:1rem; font-weight:600; color:var(--muted);
  padding:.6rem 1.1rem; border-radius:11px 11px 0 0; }
[data-testid="stTabs"] button[data-baseweb="tab"]:hover{ background:#eef0f4; color:var(--ink); }
[data-testid="stTabs"] button[aria-selected="true"]{ color:var(--brand); background:var(--brand-soft); }
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{ background:var(--brand); height:3px; border-radius:3px; }
[data-testid="stTabs"] [data-baseweb="tab-border"]{ display:none; }

/* ---- metric cards (scoreboard style) ---- */
[data-testid="stMetric"]{ background:var(--surface); border:1px solid var(--line); border-radius:16px;
  padding:1rem 1.1rem; box-shadow:0 1px 2px rgba(20,30,60,.04), 0 10px 28px rgba(20,30,60,.05); }
[data-testid="stMetricLabel"] p{ font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:500;
  letter-spacing:.06em; text-transform:uppercase; color:var(--muted2); }
[data-testid="stMetricValue"]{ font-family:'IBM Plex Mono',monospace !important; font-weight:600;
  font-size:1.7rem !important; line-height:1.2; color:var(--ink2); letter-spacing:-.01em; }

/* ---- containers, alerts, inputs, tables ---- */
[data-testid="stAlert"]{ border-radius:14px; }
[data-testid="stExpander"]{ border-radius:14px; border-color:var(--line); }
[data-testid="stExpander"] summary{ font-weight:600; }
.stDataFrame, [data-testid="stTable"]{ border:1px solid var(--line); border-radius:14px; overflow:hidden; }
[data-testid="stDataFrame"] [role="columnheader"]{ font-family:'IBM Plex Mono',monospace;
  text-transform:uppercase; letter-spacing:.04em; font-size:11px; color:var(--muted2); }
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"]{ background:var(--brand); }

/* ---- de-clutter plotly ---- */
.js-plotly-plot .modebar{ display:none !important; }
</style>
"""


def inject(brand_line: str | None = None):
    st.markdown(_CSS, unsafe_allow_html=True)
    if brand_line:
        st.markdown(
            f"<div class='appbar'><span class='dot'></span><span class='txt'>{brand_line}</span></div>",
            unsafe_allow_html=True)


def eyebrow(text: str):
    """Small uppercase mono section label in brand blue (the design's section marker)."""
    st.markdown(
        f"<div style=\"font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:12px; "
        f"letter-spacing:.14em; text-transform:uppercase; color:{BRAND}; margin-bottom:2px;\">{text}</div>",
        unsafe_allow_html=True)


def style_fig(fig, h=360, title=None):
    """Apply the design system's chart chrome to a Plotly figure."""
    fig.update_layout(
        template="plotly_white", height=h, title=title,
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=13),
        margin=dict(l=10, r=10, t=40 if title else 16, b=10),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        title_font=dict(family="Space Grotesk, sans-serif", size=15, color=INK2),
    )
    fig.update_xaxes(gridcolor=LINE2, zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE2, zeroline=False, linecolor=LINE)
    return fig


def topnav(pages, current):
    cols = st.columns(len(pages))
    for col, page in zip(cols, pages):
        is_current = page.title == current.title
        if col.button(page.title, use_container_width=True,
                      type="primary" if is_current else "secondary", key=f"nav_{page.title}"):
            st.switch_page(page)
