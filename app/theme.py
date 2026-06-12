"""Visual design system: severity tokens (UIUX_SPEC §3.1) + CSS + HTML helpers.

The UI never invents cutoffs: band NAMES come from config.PRIORITY_BANDS;
this module only assigns each name a color/icon (presentation, not semantics).
"""

import html as _html

import config as C


BAND_TOKENS = {
    "CRITICAL": {"color": "#FF4D4F", "icon": "⯃", "fg": "#121417"},
    "HIGH": {"color": "#FF9F1C", "icon": "▲", "fg": "#121417"},
    "MEDIUM": {"color": "#FFD60A", "icon": "◆", "fg": "#121417"},
    "LOW": {"color": "#34C759", "icon": "●", "fg": "#121417"},
}

assert set(BAND_TOKENS) == {b for _, b in C.PRIORITY_BANDS}, "theme tokens drifted from config.PRIORITY_BANDS"

ANOM_TOKENS = {
    "NORMAL": {"color": "#2E3440", "icon": "⚡", "fg": "#9AA3AD"},
    "WARNING": {"color": "#FF9F1C", "icon": "⚡", "fg": "#121417"},
    "CRITICAL": {"color": "#FF4D4F", "icon": "⚡", "fg": "#121417"},
}

CONSTRAINT_COLOR = "#B388FF"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Mono:wght@500&display=swap');

:root {
  --mw-bg: #121417;
  --mw-panel: #1C1F24;
  --mw-panel-2: #242932;
  --mw-line: #2A2E35;
  --mw-text: #E8EAED;
  --mw-muted: #9AA3AD;
  --mw-amber: #FF9F1C;
  --mw-red: #FF4D4F;
  --mw-yellow: #FFD60A;
  --mw-green: #34C759;
  --mw-purple: #B388FF;
  --mw-blue: #64D2FF;
  --mw-radius: 0.5rem;
  --mw-shadow: 0 0.75rem 2rem rgba(0, 0, 0, 0.28);
}

html,
body,
.stApp {
  background: var(--mw-bg);
  color: var(--mw-text);
}

body,
.stMarkdown,
.stMarkdown p,
.stMarkdown li,
.stText,
div[data-testid="stMarkdownContainer"],
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stMarkdownContainer"] li {
  font-family: 'IBM Plex Sans', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 1.125rem;
  line-height: 1.55;
  color: var(--mw-text);
}

code,
pre,
kbd,
.mw-mono,
.mw-part,
.mw-sql,
.mw-ts {
  font-family: 'IBM Plex Mono', 'Cascadia Mono', Consolas, monospace;
}

.stCaption,
div[data-testid="stCaptionContainer"],
small,
.caption {
  font-size: 0.9375rem;
  line-height: 1.4;
  color: var(--mw-muted);
}

.mw-num,
.mw-kpi,
div[data-testid="stMetricValue"],
div[data-testid="stMetricDelta"] {
  font-variant-numeric: tabular-nums;
}

.mw-num,
.mw-kpi,
div[data-testid="stMetricValue"] {
  font-size: 2.5rem;
  line-height: 1;
  font-weight: 800;
  letter-spacing: 0;
}

h2,
h3,
.mw-section-title {
  font-size: 1.375rem;
  line-height: 1.25;
  font-weight: 800;
  letter-spacing: 0;
}

#MainMenu,
footer,
[data-testid="stDeployButton"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
header[data-testid="stHeader"] {
  display: none !important;
}

.block-container {
  max-width: min(96rem, 96vw);
  padding-top: 2rem;
  padding-bottom: 2.5rem;
}

.mw-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 1.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: .04em;
  line-height: 1.25;
  text-transform: uppercase;
  white-space: nowrap;
  vertical-align: middle;
}

.mw-card {
  width: 100%;
  min-width: 0;
  border: 1px solid #2A2E35;
  border-radius: 10px;
  background: #1C1F24;
  box-shadow: var(--mw-shadow);
  padding: 16px;
}

.mw-card--critical {
  border: 2px solid #FF4D4F;
  box-shadow: 0 0 24px rgba(255,77,79,.15);
}

.mw-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
  border-left: 0.35rem solid var(--mw-amber);
  background: rgba(255, 159, 28, 0.1);
  padding: 0.75rem 1rem;
  border-radius: 0.375rem;
}

.mw-fresh--amber {
  color: var(--mw-amber);
}

.mw-fresh--red {
  color: var(--mw-red);
}

.stButton > button,
button[kind] {
  min-height: 48px;
  border-radius: 0.375rem;
  font-weight: 700;
}

.mw-cta button {
  min-height: 56px;
  font-size: 1.0625rem;
}

.stButton > button:focus-visible,
button[kind]:focus-visible,
div[role="button"]:focus-visible {
  outline: 0.1875rem solid var(--mw-amber) !important;
  outline-offset: 0.125rem !important;
  box-shadow: none !important;
}

div[role="radiogroup"] {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.25rem;
  border: 1px solid var(--mw-line);
  border-radius: 0.5rem;
  background: #171A1F;
}

div[role="radiogroup"] label {
  min-height: 2.75rem;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.55rem 1rem;
  border: 1px solid transparent;
  border-radius: 0.375rem;
  color: var(--mw-muted);
  font-weight: 800;
  text-transform: uppercase;
  cursor: pointer;
}

div[role="radiogroup"] label:hover {
  border-color: rgba(255, 159, 28, 0.5);
  color: var(--mw-text);
}

div[role="radiogroup"] label:has(input:checked),
div[role="radiogroup"] label[aria-checked="true"] {
  background: rgba(255, 159, 28, 0.16);
  border-color: var(--mw-amber);
  color: var(--mw-text);
}

div[role="radiogroup"] label:focus-within {
  outline: 0.1875rem solid var(--mw-amber);
  outline-offset: 0.125rem;
}

.mw-block {
  width: 100%;
  min-width: 0;
  margin: 1rem 0;
  padding: 1rem;
  border: 1px solid var(--mw-line);
  border-radius: 0.375rem;
  background: rgba(28, 31, 36, 0.72);
}

.mw-spark {
  width: min(100%, 16rem);
  height: 3rem;
  display: block;
  color: var(--mw-amber);
}

.mw-leadbar,
.mw-rulbar {
  --mw-bar-value: 50%;
  --mw-bar-color: var(--mw-amber);
  position: relative;
  width: 100%;
  height: 0.75rem;
  overflow: hidden;
  border-radius: 999px;
  background: #2A2F36;
}

.mw-leadbar::before,
.mw-rulbar::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: clamp(0%, var(--mw-bar-value), 100%);
  border-radius: inherit;
  background: linear-gradient(90deg, var(--mw-bar-color), rgba(255, 255, 255, 0.72));
}

.mw-rulbar {
  --mw-bar-color: var(--mw-green);
}

.mw-wall .mw-card {
  font-size: 1.8em;
}

body:has(.mw-wall) header,
body:has(.mw-wall) nav,
body:has(.mw-wall) [data-testid="stHeader"],
body:has(.mw-wall) [data-testid="stToolbar"],
body:has(.mw-wall) [data-testid="stSidebar"] {
  display: none !important;
}

@media (max-width: 48rem) {
  .block-container {
    max-width: 100vw;
    padding-left: 1rem;
    padding-right: 1rem;
  }

  div[role="radiogroup"] {
    width: 100%;
  }

  div[role="radiogroup"] label {
    flex: 1 1 min(12rem, 100%);
  }

  .mw-strip {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
"""


def esc(s) -> str:
    return _html.escape(str(s))


def _chip(text, bg, fg) -> str:
    return (f"<span class='mw-chip' style='background:{bg};color:{fg}'>"
            f"{text}</span>")


def chip(band: str) -> str:
    band = (band or "").upper()
    if band not in BAND_TOKENS:
        return _chip(f"?&nbsp;{esc(band or 'UNKNOWN')}", "#2E3440", "#9AA3AD")
    t = BAND_TOKENS[band]
    return _chip(f"{t['icon']}&nbsp;{esc(band)}", t["color"], t["fg"])


def anomaly_chip(status: str) -> str:
    status = (status or "").upper()
    if status not in ANOM_TOKENS:
        return _chip(f"?&nbsp;{esc(status or 'UNKNOWN')}", "#2E3440", "#9AA3AD")
    t = ANOM_TOKENS[status]
    return _chip(f"{t['icon']}&nbsp;{esc(status)}", t["color"], t["fg"])


def constraint_chip() -> str:
    return _chip("⛔&nbsp;PART CANNOT ARRIVE IN TIME", CONSTRAINT_COLOR, "#121417")


def mode_badge(mode: str, fell_back: bool = False) -> str:
    if fell_back:
        return _chip("⚙&nbsp;FELL BACK", "#FF9F1C", "#121417")
    if mode == "llm":
        return _chip("✦&nbsp;LLM", "#FF9F1C", "#121417")
    return _chip("⚙&nbsp;DETERMINISTIC (offline-capable)", "#2E3440", "#9AA3AD")


def alert_level_chip(level: str) -> str:
    lv = (level or "").upper()
    if "CRITICAL" in lv:
        return chip("CRITICAL") if lv == "CRITICAL" else _chip(f"⚡&nbsp;{esc(lv)}", BAND_TOKENS["CRITICAL"]["color"], "#121417")
    if lv in BAND_TOKENS:
        return chip(lv)
    return _chip(esc(lv or "INFO"), "#2E3440", "#9AA3AD")


def inject():
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
