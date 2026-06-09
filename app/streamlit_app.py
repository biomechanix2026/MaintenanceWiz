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
from agent import tools as T
from agent.orchestrator import run_agent
from agent.tools import (risk_score_tool, prognostic_tool, inventory_tool,
                         delay_history_tool, rag_tool, resolve_asset,
                         task_closure_tool, append_logbook, record_feedback,
                         learned_bias, CLOSURE_ITEMS)
from ml.model import load_model

st.set_page_config(page_title="Maintenance Wizard", page_icon="🛠️", layout="wide")

BAND_COLOR = {"CRITICAL": "#c0392b", "HIGH": "#e67e22",
              "MEDIUM": "#f1c40f", "LOW": "#27ae60"}


# --------------------------------------------------------------------------
# Cached loaders
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def registry():
    return pd.read_csv(C.ASSET_REGISTRY_CSV)

@st.cache_data(show_spinner="Scoring all assets...")
def plant_scan():
    rows = []
    reg = registry()
    for _, a in reg.iterrows():
        r = risk_score_tool(a["asset_id"])
        rows.append({
            "asset_id": a["asset_id"], "name": a["name"], "line": a["line"],
            "criticality": a["criticality"], "priority_score": r["priority_score"],
            "band": r["priority_band"], "rul_days": r["rul_days"],
            "constraint": "⚠️" if r.get("constraint_flag") else "",
        })
    return pd.DataFrame(rows).sort_values("priority_score", ascending=False)


def band_badge(band):
    return f"<span style='background:{BAND_COLOR[band]};color:white;padding:2px 10px;border-radius:10px;font-weight:600'>{band}</span>"


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
mode = "LLM (Claude)" if os.environ.get("ANTHROPIC_API_KEY") else "Deterministic (offline)"
model = load_model()
st.title("🛠️ Maintenance Wizard")
st.caption(f"Consolidated-Brain agent for a heavy steel plant · engine mode: **{mode}** · "
           f"prognostic model: **{model.kind}** · {datetime.now():%Y-%m-%d %H:%M}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Plant Bottleneck", "🔬 Asset Deep-Dive", "💬 Wizard Chat",
     "🌅 Pre-Shift Report", "📒 Digital Logbook"])


# ==========================================================================
# TAB 1 - Plant Bottleneck View
# ==========================================================================
with tab1:
    st.subheader("Plant-wide triage")
    df = plant_scan()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Assets monitored", len(df))
    c2.metric("Critical", int((df.band == "CRITICAL").sum()))
    c3.metric("High", int((df.band == "HIGH").sum()))
    c4.metric("Constraint-flagged", int((df.constraint == "⚠️").sum()))

    st.bar_chart(df.set_index("asset_id")["priority_score"], height=260)
    st.dataframe(
        df.rename(columns={"asset_id": "Asset", "name": "Name", "line": "Line",
                           "priority_score": "Priority", "band": "Band",
                           "rul_days": "RUL (d)", "constraint": "Flag"}),
        hide_index=True, use_container_width=True)
    st.caption("⚠️ = part lead time exceeds predicted RUL → repair cannot complete "
               "in time; the agent switches to a monitored-degradation strategy.")


# ==========================================================================
# TAB 2 - Asset Deep-Dive (interactive workbook)
# ==========================================================================
with tab2:
    reg = registry()
    aid = st.selectbox("Asset", reg.asset_id, key="deep_asset")
    arow = reg[reg.asset_id == aid].iloc[0]
    prog = prognostic_tool(aid)
    risk = risk_score_tool(aid)

    left, right = st.columns([1, 1])
    with left:
        st.markdown(f"**{arow['name']}** · {arow['type']} · {arow['line']}  "
                    f"{band_badge(risk['priority_band'])}", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("Priority", f"{risk['priority_score']}/100")
        m2.metric("RUL", f"{prog['rul_days']} d")
        m3.metric("Fail prob (30d)", f"{prog['failure_probability_30d']:.0%}")
        if risk.get("constraint_flag"):
            st.warning(risk["constraint_flag"])

        st.markdown("**Spare parts (ERP)**")
        st.dataframe(pd.DataFrame(inventory_tool(aid)["parts"]),
                     hide_index=True, use_container_width=True)

    with right:
        st.markdown("**SHAP feature attribution** — why the model predicts this RUL")
        shap = prog["shap"]
        contrib = shap["contributions"]
        cdf = pd.DataFrame({"feature": list(contrib.keys()),
                            "contribution_days": list(contrib.values())}).set_index("feature")
        st.bar_chart(cdf, height=240)
        st.caption(f"Method: {shap['method']}. Negative bars push RUL **down** "
                   f"(accelerate failure). Top driver: **{shap['top_driver']}**.")

        with st.expander("🔧 Workbook: adjust sensor inputs and recompute"):
            st.caption("Validate the model by perturbing the live readings.")
            new = {}
            for f, v in prog["latest_readings"].items():
                new[f] = st.slider(f, float(v) * 0.5, float(v) * 1.5, float(v), key=f"sl_{aid}_{f}")
            rul2 = model.predict_rul(arow["type"], new)
            st.metric("Recomputed RUL", f"{rul2:.1f} d", f"{rul2 - prog['rul_days']:+.1f} d")


# ==========================================================================
# TAB 3 - Wizard Chat
# ==========================================================================
with tab3:
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
            with st.spinner("Thinking → acting → observing..."):
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
# TAB 4 - Pre-Shift Report (System of Action: work done before you log in)
# ==========================================================================
with tab4:
    st.subheader("🌅 Pre-shift autonomous report")
    st.caption("Generated by the agent on a schedule — before anyone logs in. "
               "Every flagged asset already has a drafted work order.")
    df = plant_scan()
    urgent = df[df.band.isin(["CRITICAL", "HIGH"])]
    st.markdown(f"**{len(urgent)}** assets need attention this shift "
                f"({int((df.band=='CRITICAL').sum())} critical).")
    for _, r in urgent.iterrows():
        with st.expander(f"{r['band']} · {r['asset_id']} — {r['name']} "
                         f"(score {r['priority_score']}, RUL {r['rul_days']}d) {r['constraint']}"):
            prog = prognostic_tool(r["asset_id"])
            inv = inventory_tool(r["asset_id"])
            out = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
            st.markdown(f"- **Top driver:** {prog['shap']['top_driver']}")
            st.markdown(f"- **Drafted work order:** inspect/repair per "
                        f"SOP for {r['asset_id']}; "
                        + (f"order long-lead parts now: {', '.join(p['part_no'] for p in out)}."
                           if out else "required parts in stock."))
            risk = risk_score_tool(r["asset_id"])
            if risk.get("constraint_flag"):
                st.warning("Constraint: " + risk["constraint_flag"])


# ==========================================================================
# TAB 5 - Digital Logbook + closure checklist (loop closure / compliance)
# ==========================================================================
with tab5:
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
