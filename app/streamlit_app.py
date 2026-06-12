"""
Maintenance Wizard - Streamlit dashboard.

Design philosophy: "AI to build, UI to validate." Every AI output is paired
with the raw evidence behind it (the SQL it ran, the SOP sections it cited,
the SHAP attribution, the full tool trace) so an engineer can interrogate the
reasoning, "riff" on the parameters, and only then act.

Panels
  1. Plant Bottleneck View  - every asset ranked by priority score (triage)
  2. Asset Deep-Dive        - sensors, SHAP, parts; interactive workbook controls
  3. Wizard Chat            - ask in plain English, get the 5-block answer + trace
  4. Pre-Shift Report       - autonomous run; drafted work orders before login
  5. Digital Logbook        - closure checklist + feedback loop

Run:  streamlit run app/streamlit_app.py
"""
import os
import sys
import json
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from app import theme as TH, components as UI
from agent import tools as T
from agent.orchestrator import run_agent
from agent.tools import (risk_score_tool, prognostic_tool, inventory_tool,
                         abnormality_tool, delay_history_tool, rag_tool, resolve_asset,
                         task_closure_tool, append_logbook, record_feedback,
                         learned_bias, CLOSURE_ITEMS)
from ml.model import load_model

st.set_page_config(page_title="Maintenance Wizard", page_icon="🛠️", layout="wide")
TH.inject()

BAND_COLOR = {"CRITICAL": "#c0392b", "HIGH": "#e67e22",
              "MEDIUM": "#f1c40f", "LOW": "#27ae60"}


# --------------------------------------------------------------------------
# Cached loaders
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def registry():
    return pd.read_csv(C.ASSET_REGISTRY_CSV)


@st.cache_data(ttl=300, show_spinner="Scoring all assets...")
def plant_scan():
    rows = []
    reg = registry()
    for _, a in reg.iterrows():
        r = risk_score_tool(a["asset_id"])
        abn = abnormality_tool(a["asset_id"])
        constraint_flag = r.get("constraint_flag")
        rows.append({
            "asset_id": a["asset_id"], "name": a["name"], "line": a["line"],
            "criticality": a["criticality"], "priority_score": r["priority_score"],
            "band": r["priority_band"], "priority_band": r["priority_band"],
            "rul_days": r["rul_days"], "anomaly_status": abn["status"],
            "anomaly_score": abn["anomaly_score"],
            "constraint_flag": constraint_flag,
            "constraint": "⚠️" if constraint_flag else "",
        })
    return pd.DataFrame(rows).sort_values("priority_score", ascending=False)


def band_badge(band):
    return f"<span style='background:{BAND_COLOR[band]};color:white;padding:2px 10px;border-radius:10px;font-weight:600'>{band}</span>"


def _fmt_rul(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{num:.0f} d"


def _wallboard_card_html(row) -> str:
    asset_id = str(row.get("asset_id", ""))
    name = str(row.get("name", "Unknown asset"))
    line = str(row.get("line", "Unknown line"))
    band = str(row.get("priority_band", row.get("band", "LOW"))).upper()
    anomaly = str(row.get("anomaly_status", "NORMAL")).upper()
    score = int(round(float(row.get("priority_score", 0) or 0)))
    constraint_html = ""
    if row.get("constraint_flag"):
        constraint_html = f"<div style='margin-top:.7rem'>{TH.constraint_chip()}</div>"

    return f"""
      <div class="mw-card {'mw-card--critical' if band == 'CRITICAL' else ''}">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:.75rem;flex-wrap:wrap">
          <div>{TH.chip(band)}</div>
          <div class="mw-mono" style="font-size:1.35rem;font-weight:800">{score:02d}/100</div>
        </div>
        <div style="margin-top:.85rem;font-size:1.05rem;font-weight:800">{TH.esc(asset_id)} · {TH.esc(name)} · {TH.esc(line)}</div>
        <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-top:.75rem">
          <span class="mw-mono">RUL {TH.esc(_fmt_rul(row.get("rul_days")))}</span>
          {TH.anomaly_chip(anomaly)}
        </div>
        {constraint_html}
      </div>
    """


def _render_wallboard_body():
    plant_scan.clear()
    df = plant_scan().head(6)
    if df.empty:
        st.info("No plant scan rows available.")
        return

    cards = "\n".join(_wallboard_card_html(row) for _, row in df.iterrows())
    st.markdown(
        f"""
        <style>
          body:has(.mw-wall) .block-container {{
            max-width: min(112rem, 98vw);
            padding-top: 1rem;
          }}
          .mw-wall {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
          }}
          @media (max-width: 64rem) {{
            .mw-wall {{
              grid-template-columns: 1fr;
            }}
          }}
        </style>
        <div class="mw-wall">
          {cards}
        </div>
        """,
        unsafe_allow_html=True,
    )


if hasattr(st, "fragment"):
    render_wallboard = st.fragment(run_every=300)(_render_wallboard_body)
else:
    def render_wallboard():
        st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)
        _render_wallboard_body()


def _kpi_card(label: str, value: int):
    st.markdown(
        f"""
        <div class="mw-card" style="box-shadow:none">
          <div class="mw-num">{int(value)}</div>
          <div style="color:var(--mw-muted);font-weight:800;text-transform:uppercase">{TH.esc(label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_row(df: pd.DataFrame):
    metrics = [
        ("Assets monitored", len(df)),
        ("Critical", int((df.band == "CRITICAL").sum())),
        ("High", int((df.band == "HIGH").sum())),
        ("Abnormal", int((df.anomaly_status != "NORMAL").sum())),
        ("Constraint-flagged", int(df.constraint_flag.notna().sum())),
    ]
    for col, (label, value) in zip(st.columns(5), metrics):
        with col:
            _kpi_card(label, value)


def _with_asset_types(df: pd.DataFrame) -> pd.DataFrame:
    types = registry()[["asset_id", "type"]]
    return df.merge(types, on="asset_id", how="left")


def _ordered_bands(values) -> list[str]:
    config_order = [band for _, band in C.PRIORITY_BANDS]
    present = {str(v) for v in values if pd.notna(v)}
    return [band for band in config_order if band in present]


def _render_asset_grid(df: pd.DataFrame):
    if df.empty:
        st.info("No assets match the current filters.")
        return

    critical = df[df.band == "CRITICAL"]
    remainder = df[df.band != "CRITICAL"]

    for _, row in critical.iterrows():
        UI.asset_card(row, full_width=True)

    if not remainder.empty:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(remainder.iterrows()):
            with cols[idx % 3]:
                UI.asset_card(row)


def _render_density_view(df: pd.DataFrame):
    columns = [
        "asset_id", "name", "type", "line", "criticality", "priority_score",
        "band", "rul_days", "anomaly_status", "anomaly_score", "constraint",
    ]
    table = df[columns].rename(columns={
        "asset_id": "Asset",
        "name": "Name",
        "type": "Type",
        "line": "Line",
        "criticality": "Criticality",
        "priority_score": "Priority",
        "band": "Band",
        "rul_days": "RUL (d)",
        "anomaly_status": "Anomaly",
        "anomaly_score": "Anomaly Score",
        "constraint": "Flag",
    })
    st.dataframe(table, hide_index=True, use_container_width=True)


if st.query_params.get("wallboard") == "1":
    render_wallboard()
    st.stop()

model = load_model()
engine_mode = "llm" if os.environ.get("ANTHROPIC_API_KEY") else "deterministic"
UI.status_strip(engine_mode, model.kind)
view = UI.nav()


# ==========================================================================
# VIEW 1 - Plant Bottleneck View
# ==========================================================================
if view == UI.VIEWS[0]:
    st.subheader("Plant-wide triage")
    df = _with_asset_types(plant_scan())
    _render_kpi_row(df)

    band_options = _ordered_bands(df["band"])
    type_options = sorted(df["type"].dropna().unique().tolist())
    line_options = sorted(df["line"].dropna().unique().tolist())

    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    with f1:
        bands = st.multiselect("Band", band_options, default=band_options)
    with f2:
        types = st.multiselect("Type", type_options, default=type_options)
    with f3:
        lines = st.multiselect("Line", line_options, default=line_options)
    with f4:
        st.write("")
        if st.button("⟳ Rescan", use_container_width=True):
            plant_scan.clear()
            UI.clear_data_caches()
            st.rerun()

    filtered = df[
        df["band"].isin(bands)
        & df["type"].isin(types)
        & df["line"].isin(lines)
    ].sort_values("priority_score", ascending=False)

    _render_asset_grid(filtered)
    st.caption("⚠️ = part lead time exceeds predicted RUL -> repair cannot complete "
               "in time; the agent switches to a monitored-degradation strategy. "
               "Anomaly is an independent sensor-deviation early-warning signal.")

    with st.expander("Engineer density view"):
        _render_density_view(filtered)


# ==========================================================================
# VIEW 2 - Asset Deep-Dive (interactive workbook)
# ==========================================================================
if view == UI.VIEWS[1]:
    reg = registry()
    asset_ids = reg.asset_id.astype(str).tolist()
    default_asset = st.session_state.get("deep_asset", asset_ids[0])
    default_index = asset_ids.index(default_asset) if default_asset in asset_ids else 0
    aid = st.selectbox("Asset", asset_ids, index=default_index, key="deep_asset")
    arow = reg[reg.asset_id == aid].iloc[0]
    prog = prognostic_tool(aid)
    abn = abnormality_tool(aid)
    risk = risk_score_tool(aid)

    constraint_html = ""
    if risk.get("constraint_flag"):
        constraint_html = f"<div style='margin-top:.8rem'>{TH.constraint_chip()}</div>"
    st.markdown(
        f"""
        <div class="mw-card {'mw-card--critical' if risk['priority_band'] == 'CRITICAL' else ''}">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap">
            <div>
              <div class="mw-mono" style="font-size:1.6rem;font-weight:800">{TH.esc(aid)}</div>
              <div style="font-size:1.1rem;font-weight:800">{TH.esc(arow['name'])}</div>
              <div style="color:var(--mw-muted);font-weight:700">{TH.esc(arow['type'])} | {TH.esc(arow['line'])}</div>
            </div>
            <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;justify-content:flex-end">
              {TH.chip(risk['priority_band'])}
              {TH.anomaly_chip(abn['status'])}
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;margin-top:1rem">
            <div>
              <div style="color:var(--mw-muted);font-weight:800;text-transform:uppercase;font-size:.78rem">score</div>
              <div class="mw-mono" style="font-size:1.5rem;font-weight:800">{risk['priority_score']}/100</div>
            </div>
            <div>
              <div style="color:var(--mw-muted);font-weight:800;text-transform:uppercase;font-size:.78rem">RUL</div>
              <div class="mw-mono" style="font-size:1.5rem;font-weight:800">{prog['rul_days']} d</div>
            </div>
            <div>
              <div style="color:var(--mw-muted);font-weight:800;text-transform:uppercase;font-size:.78rem">fail-prob 30d</div>
              <div class="mw-mono" style="font-size:1.5rem;font-weight:800">{prog['failure_probability_30d']:.0%}</div>
            </div>
          </div>
          {constraint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Live sensor evidence**")
    UI.sensor_tiles(aid, arow["type"])

    st.markdown("**SHAP feature attribution**")
    UI.shap_bars(prog["shap"])

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-top:.75rem">
          {TH.anomaly_chip(abn['status'])}
          <span style="font-weight:800">Independent abnormality evidence</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if abn["status"] == "CRITICAL":
        st.error(abn["recommendation"])
    elif abn["status"] == "WARNING":
        st.warning(abn["recommendation"])
    else:
        st.info(abn["recommendation"])
    evidence = pd.DataFrame(abn["breached_features"] or abn["trend_features"])
    st.dataframe(evidence, hide_index=True, use_container_width=True)

    st.markdown("**Spare parts (ERP)**")
    UI.parts_panel(inventory_tool(aid), prog["rul_days"])

    with st.expander("🔧 Workbook: adjust sensor inputs and recompute"):
        st.caption("Validate the model by perturbing the live readings.")
        new = {}
        for f, v in prog["latest_readings"].items():
            new[f] = st.slider(f, float(v) * 0.5, float(v) * 1.5, float(v), key=f"sl_{aid}_{f}")
        rul2 = model.predict_rul(arow["type"], new)
        st.metric("Recomputed RUL", f"{rul2:.1f} d", f"{rul2 - prog['rul_days']:+.1f} d")

    st.markdown("**SOP & incident evidence**")
    rag = rag_tool("isolation repair procedure", asset_id=aid, k=4)
    hits = rag.get("results", [])
    incident_hits = [h for h in hits if str(h.get("type", "")).lower() == "incident"]
    for hit in hits:
        hit_type = str(hit.get("type", "")).lower()
        icon = "📘" if hit_type == "manual" else "⚠️" if hit_type == "incident" else "📄"
        source = hit.get("source", "source")
        with st.expander(f"{icon} {source}"):
            st.markdown(hit.get("text", ""))
            if "score" in hit:
                st.caption(f"Retrieval score: {hit['score']}")
    if not incident_hits:
        st.info("No prior incidents on record")

    st.markdown('<div class="mw-cta">', unsafe_allow_html=True)
    if st.button("💬 Ask the Wizard about this asset", key=f"ask_wizard_{aid}", use_container_width=True):
        UI.goto(UI.VIEWS[2], last_asset=aid, chat_prefill=f"What's wrong with {aid}?")
    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================================================
# VIEW 3 - Wizard Chat
# ==========================================================================
if view == UI.VIEWS[2]:
    st.subheader("Ask the Wizard")
    st.caption("Try: *what's wrong with the mill gearbox?* · "
               "*that valve that keeps leaking on the caster* · *cooling pump status*")
    if "chat" not in st.session_state:
        st.session_state.chat = []

    q = st.chat_input("Describe the asset, alert, or symptom...")
    for turn in st.session_state.chat:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"], unsafe_allow_html=True)

    if q:
        st.session_state.chat.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Thinking -> acting -> observing..."):
                # Pass prior turns + the asset in focus so follow-ups
                # ("what about its bearings?") stay context-aware.
                history = st.session_state.chat[:-1]
                res = run_agent(q, history=history,
                                focus_asset=st.session_state.get("last_asset"))
            st.markdown(res.answer_markdown)
            with st.expander(f"🧠 Tool trace ({len(res.trace)} calls · mode={res.mode})"):
                for step in res.trace:
                    st.markdown(f"**{step['tool']}** `{json.dumps(step['input'])}`")
                    st.json(step["output"], expanded=False)
            if res.asset_id:
                st.session_state.last_asset = res.asset_id
        st.session_state.chat.append({"role": "assistant", "content": res.answer_markdown})


# ==========================================================================
# VIEW 4 - Pre-Shift Report (System of Action: work done before you log in)
# ==========================================================================
if view == UI.VIEWS[3]:
    st.subheader("🌅 Pre-shift autonomous report")
    st.caption("Generated by the agent on a schedule — before anyone logs in. "
               "Every flagged asset already has a drafted work order.")
    df = plant_scan()
    urgent = df[df.band.isin(["CRITICAL", "HIGH"]) | (df.anomaly_status != "NORMAL")]
    st.markdown(f"**{len(urgent)}** assets need attention this shift "
                f"({int((df.band=='CRITICAL').sum())} critical, "
                f"{int((df.anomaly_status!='NORMAL').sum())} abnormal).")
    for _, r in urgent.iterrows():
        with st.expander(f"{r['band']} · {r['asset_id']} — {r['name']} "
                         f"(score {r['priority_score']}, RUL {r['rul_days']}d, "
                         f"anomaly {r['anomaly_status']}) {r['constraint']}"):
            prog = prognostic_tool(r["asset_id"])
            abn = abnormality_tool(r["asset_id"])
            inv = inventory_tool(r["asset_id"])
            out = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
            st.markdown(f"- **Top driver:** {prog['shap']['top_driver']}")
            st.markdown(f"- **Abnormality:** {abn['status']} ({abn['anomaly_score']}/100); "
                        f"{abn['recommendation']}")
            st.markdown(f"- **Drafted work order:** inspect/repair per "
                        f"SOP for {r['asset_id']}; "
                        + (f"order long-lead parts now: {', '.join(p['part_no'] for p in out)}."
                           if out else "required parts in stock."))
            risk = risk_score_tool(r["asset_id"])
            if risk.get("constraint_flag"):
                st.warning("Constraint: " + risk["constraint_flag"])


# ==========================================================================
# VIEW 5 - Digital Logbook + closure checklist (loop closure / compliance)
# ==========================================================================
if view == UI.VIEWS[4]:
    st.subheader("📒 Digital logbook & job closure")
    reg = registry()
    aid = st.selectbox("Asset", reg.asset_id,
                       index=int(reg.asset_id.tolist().index(
                           st.session_state.get("last_asset", reg.asset_id.iloc[0]))),
                       key="log_asset")
    wo = st.text_input("Work order ID", value=f"WO-{aid}-{datetime.now():%m%d}")

    st.markdown("**Compliance checklist** — the agent blocks closure until all are green.")
    checks = {}
    labels = {"parts_recorded": "Parts used recorded",
              "steps_logged": "Repair steps logged",
              "isolation_cleared": "Safety isolation cleared",
              "follow_up_scheduled": "Follow-up inspection scheduled",
              "digital_logbook_entry": "Logbook entry written"}
    cols = st.columns(len(CLOSURE_ITEMS))
    for col, item in zip(cols, CLOSURE_ITEMS):
        checks[item] = col.checkbox(labels[item], key=f"chk_{item}")

    note = st.text_area("Engineer notes (fed back into the knowledge base)", "")

    st.markdown("**Feedback to the agent** — corrections here improve future diagnoses "
                "and priority scores for this asset.")
    correction = st.text_input("Diagnosis correction (what the agent got wrong / confirmed)",
                               key="fb_correction")
    sev = st.slider("Urgency adjustment vs the agent's score", -25, 25, 0, key="fb_sev",
                    help="Negative = agent over-scored urgency; positive = under-scored. "
                         "Applied to this asset's future priority.")
    _bias, _n = learned_bias(aid)
    if _n:
        st.caption(f"🧠 Already learned from **{_n}** feedback record(s) on {aid} "
                   f"(priority Δ {_bias:+.1f}).")

    closure = task_closure_tool(wo, checks)
    if closure["can_close"]:
        st.success(closure["message"])
    else:
        st.error(closure["message"])

    if st.button("Close & log job", disabled=not closure["can_close"]):
        append_logbook({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "work_order_id": wo, "asset_id": aid, "notes": note,
            "closed_by": "engineer",
        })
        fb = record_feedback(aid, work_order_id=wo, note=note,
                             correction=correction, severity_adjust=sev,
                             outcome="job_closed")
        plant_scan.clear()  # priority scores changed -> refresh cached triage
        st.success(f"{wo} closed and written to the digital logbook. " + fb["message"])

    if os.path.exists(C.LOGBOOK_CSV):
        st.markdown("**Recent logbook entries**")
        st.dataframe(pd.read_csv(C.LOGBOOK_CSV).tail(10), hide_index=True,
                     use_container_width=True)
