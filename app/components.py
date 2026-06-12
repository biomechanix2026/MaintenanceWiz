import os
import json
import re
import hashlib
import datetime

import streamlit as st
import altair as alt
import pandas as pd

import config as C
from app import theme as TH


VIEWS = ["📊 Plant Bottleneck", "🔬 Asset Deep-Dive", "💬 Wizard Chat", "🌅 Pre-Shift Report", "📒 Digital Logbook"]

BLOCK_META = {
    1: ("🛑", True),
    2: ("🔬", True),
    3: ("🧰", True),
    4: ("📦", False),
    5: ("🧾", False),
}


@st.cache_data(ttl=300, show_spinner=False)
def sensor_log() -> pd.DataFrame:
    return pd.read_csv(C.SENSOR_LOGS_CSV)


def clear_data_caches():
    sensor_log.clear()


def _is_missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _row_value(row, *names, default=None):
    sentinel = object()
    for name in names:
        if isinstance(row, dict) and name in row:
            value = row[name]
            if not _is_missing(value):
                return value
        if hasattr(row, "get"):
            try:
                value = row.get(name, sentinel)
            except TypeError:
                value = sentinel
            if value is not sentinel and not _is_missing(value):
                return value
        if hasattr(row, name):
            value = getattr(row, name)
            if not _is_missing(value):
                return value
        if hasattr(row, "_asdict"):
            data = row._asdict()
            if name in data and not _is_missing(data[name]):
                return data[name]
    return default


def _to_float(value, default=0.0) -> float:
    try:
        if _is_missing(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_number(value, digits=1) -> str:
    num = _to_float(value)
    if abs(num - round(num)) < 0.05:
        return f"{round(num):.0f}"
    return f"{num:.{digits}f}"


def _jsonable(value):
    try:
        return json.loads(json.dumps(value, default=str, ensure_ascii=False))
    except (TypeError, ValueError):
        return str(value)


def _json_inline(value) -> str:
    text = json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)
    return text.replace("`", "\\`")


def _status_chip(text: str, bg: str, fg: str = "#121417") -> str:
    return f"<span class='mw-chip' style='background:{bg};color:{fg}'>{TH.esc(text)}</span>"


def _latest_sensor_timestamp(log: pd.DataFrame):
    if log.empty or "timestamp" not in log.columns:
        return None
    ts = pd.to_datetime(log["timestamp"], errors="coerce").max()
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _freshness(timestamp) -> tuple[str, str]:
    if timestamp is None:
        return "--:--", "mw-fresh--red"
    now = datetime.datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.datetime.now()
    age = now - timestamp
    css_class = ""
    if age > datetime.timedelta(hours=8):
        css_class = "mw-fresh--red"
    elif age > datetime.timedelta(hours=2):
        css_class = "mw-fresh--amber"
    return timestamp.strftime("%H:%M"), css_class


def _alerts_sent_today() -> int:
    path = os.path.join(C.DATA_DIR, "notifications.jsonl")
    today = datetime.datetime.now().date().isoformat()
    count = 0
    if not os.path.exists(path):
        return count
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(payload.get("ts", "")).startswith(today):
                count += 1
    return count


def status_strip(engine_mode, model_kind):
    log = sensor_log()
    time_label, fresh_class = _freshness(_latest_sensor_timestamp(log))
    alerts_today = _alerts_sent_today()
    st.markdown(
        f"""
        <div class="mw-strip">
          <div>{TH.mode_badge(engine_mode)} <span class="mw-chip" style="background:#242932;color:#E8EAED">prognostic model: {TH.esc(model_kind)}</span></div>
          <div class="mw-mono" style="display:flex;gap:.9rem;flex-wrap:wrap">
            <span class="{fresh_class}">data as of {TH.esc(time_label)}</span>
            <span>alerts sent today: {alerts_today}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def nav() -> str:
    if "nav" not in st.session_state:
        st.session_state.nav = VIEWS[0]
    return st.radio("View", VIEWS, key="nav", horizontal=True, label_visibility="collapsed")


def goto(view: str, **state):
    st.session_state.update(state)
    st.session_state.nav = view
    st.rerun()


def asset_card(row, *, full_width=False):
    asset_id = str(_row_value(row, "asset_id", "Asset", default=""))
    name = _row_value(row, "name", "Name", default="Unknown asset")
    line = _row_value(row, "line", "Line", default="Unknown line")
    band = str(_row_value(row, "priority_band", "band", "Band", default="LOW")).upper()
    score = int(round(_to_float(_row_value(row, "priority_score", "Priority", "score", default=0))))
    rul_days = _row_value(row, "rul_days", "RUL (d)", "rul", default=None)
    anomaly = str(_row_value(row, "anomaly_status", "Anomaly", "status", default="NORMAL")).upper()
    constraint = _row_value(row, "constraint_flag", "constraint", "Flag", default="")
    is_constraint = bool(constraint)
    card_class = "mw-card mw-card--critical" if band == "CRITICAL" else "mw-card"
    rul_text = "n/a" if rul_days is None else f"{_fmt_number(rul_days, 0)} d"
    constraint_html = f"<div style='margin-top:.7rem'>{TH.constraint_chip()}</div>" if is_constraint else ""
    width_style = "width:100%;" if full_width else ""

    st.markdown(
        f"""
        <div class="{card_class}" style="{width_style}">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:.75rem;flex-wrap:wrap">
            <div>{TH.chip(band)}</div>
            <div class="mw-mono" style="font-size:1.35rem;font-weight:800">{score:02d}/100</div>
          </div>
          <div style="margin-top:.85rem;font-size:1.05rem;font-weight:800">{TH.esc(asset_id)} · {TH.esc(name)} · {TH.esc(line)}</div>
          <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-top:.75rem">
            <span class="mw-mono">RUL {TH.esc(rul_text)}</span>
            {TH.anomaly_chip(anomaly)}
          </div>
          {constraint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Deep-Dive →", key=f"dd_{asset_id}", use_container_width=full_width):
        goto(VIEWS[1], deep_asset=asset_id)


def _z_color(z: float | None) -> str:
    if z is None:
        return "#9AA3AD"
    az = abs(z)
    if az >= C.ANOMALY_CRITICAL_Z:
        return "#FF4D4F"
    if az >= C.ANOMALY_WARNING_Z:
        return "#FF9F1C"
    return "#34C759"


def sensor_tiles(asset_id, asset_type):
    log = sensor_log()
    if "asset_id" not in log.columns:
        st.info("No sensor history available.")
        return
    rows = log[log["asset_id"].astype(str) == str(asset_id)].copy()
    if "timestamp" in rows.columns:
        rows["timestamp"] = pd.to_datetime(rows["timestamp"], errors="coerce")
        rows = rows.sort_values("timestamp")
    rows = rows.tail(48)
    if rows.empty:
        st.info("No sensor history available.")
        return

    nominal = C.NOMINAL.get(str(asset_type).lower(), {})
    latest = rows.iloc[-1]
    cols = st.columns(len(C.SENSOR_FEATURES))
    for col, feature in zip(cols, C.SENSOR_FEATURES):
        with col:
            current = pd.to_numeric(pd.Series([latest.get(feature)]), errors="coerce").iloc[0]
            baseline = nominal.get(feature)
            z = None
            if baseline and not pd.isna(current):
                mean, sigma = baseline
                if sigma:
                    z = (float(current) - float(mean)) / float(sigma)
            color = _z_color(z)
            sigma_text = "n/a σ" if z is None else f"{z:+.1f}σ vs nominal"
            st.markdown(
                f"""
                <div class="mw-card" style="box-shadow:none;padding:.75rem;border-left:4px solid {color}">
                  <div style="font-weight:800;text-transform:uppercase;color:#9AA3AD;font-size:.78rem">{TH.esc(feature)}</div>
                  <div class="mw-mono" style="font-size:1.45rem;font-weight:800;color:#E8EAED">{TH.esc(_fmt_number(current))}</div>
                  <div class="mw-mono" style="color:{color};font-size:.88rem">{TH.esc(sigma_text)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            chart_rows = rows[["timestamp", feature]].copy() if "timestamp" in rows.columns and feature in rows.columns else pd.DataFrame()
            if not chart_rows.empty:
                chart_rows[feature] = pd.to_numeric(chart_rows[feature], errors="coerce")
                chart_rows = chart_rows.dropna(subset=[feature])
            if not chart_rows.empty:
                chart = (
                    alt.Chart(chart_rows)
                    .mark_line(color=color)
                    .encode(
                        x=alt.X("timestamp:T", axis=None),
                        y=alt.Y(f"{feature}:Q", axis=None),
                    )
                    .properties(height=56)
                    .configure_view(strokeWidth=0)
                )
                st.altair_chart(chart, use_container_width=True)
            st.caption(sigma_text)


def shap_bars(shap):
    contributions = (shap or {}).get("contributions") or {}
    if not contributions:
        st.caption("No feature attribution available.")
        return

    rows = [
        {"feature": feature, "contribution_days": _to_float(value), "abs_days": abs(_to_float(value))}
        for feature, value in contributions.items()
    ]
    rows = sorted(rows, key=lambda item: item["abs_days"], reverse=True)
    df = pd.DataFrame(rows)
    feature_order = df["feature"].tolist()
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("contribution_days:Q", title="Δ RUL (days)"),
            y=alt.Y("feature:N", sort=feature_order, title=None),
            color=alt.condition("datum.contribution_days < 0", alt.value("#FF4D4F"), alt.value("#34C759")),
            tooltip=["feature:N", alt.Tooltip("contribution_days:Q", format=".2f")],
        )
        .properties(height=max(120, 32 * len(df)))
    )
    st.altair_chart(chart, use_container_width=True)

    top = rows[0]["feature"]
    deviations = (shap or {}).get("deviations") or {}
    top_dev = deviations.get(top)
    if isinstance(top_dev, dict):
        top_dev = top_dev.get("z", top_dev.get("sigma", top_dev.get("deviation")))
    if top_dev is not None:
        driver = f"Top driver: {top} at {_to_float(top_dev):+.1f}σ."
    else:
        driver = f"Top driver: {top}."
    method = (shap or {}).get("method", "unknown attribution")
    st.caption(f"{driver} Negative bars reduce predicted RUL; positive bars extend it. Attribution method: {method}.")


def parts_panel(inv, rul_days):
    parts = inv.get("parts", inv) if isinstance(inv, dict) else inv
    parts = parts or []
    rul = max(_to_float(rul_days), 0.0)
    if not parts:
        st.caption("No spare-parts inventory returned.")
        return

    for idx, part in enumerate(parts):
        part_no = _row_value(part, "part_no", "part_number", "sku", default=f"PART-{idx + 1}")
        desc = _row_value(part, "description", "name", default="No description")
        qty = int(round(_to_float(_row_value(part, "qty_on_hand", "quantity", "stock", default=0))))
        lead = max(_to_float(_row_value(part, "lead_time_days", "lead_days", "lead_time", default=0)), 0.0)
        scale = max(lead, rul, 1.0)
        lead_width = (lead / scale) * 100
        rul_width = (rul / scale) * 100
        lead_color = "#B388FF" if lead > rul else "#FF9F1C"
        stock_chip = _status_chip(f"IN STOCK · {qty}", "#34C759") if qty > 0 else _status_chip("OUT OF STOCK", "#FF4D4F")
        st.markdown(
            f"""
            <div class="mw-card" style="box-shadow:none;margin-bottom:.75rem">
              <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap">
                <div>
                  <div class="mw-mono" style="font-weight:800">{TH.esc(part_no)}</div>
                  <div style="color:#E8EAED">{TH.esc(desc)}</div>
                </div>
                {stock_chip}
              </div>
              <div style="display:grid;grid-template-columns:minmax(5rem,7rem) 1fr;gap:.45rem .75rem;align-items:center;margin-top:.9rem">
                <div class="mw-mono">lead {_fmt_number(lead, 0)} d</div>
                <div class="mw-leadbar" style="--mw-bar-value:{lead_width:.2f}%;--mw-bar-color:{lead_color}"></div>
                <div class="mw-mono">RUL {_fmt_number(rul, 0)} d</div>
                <div class="mw-rulbar" style="--mw-bar-value:{rul_width:.2f}%"></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _split_block(raw: str) -> tuple[str, str]:
    lines = raw.strip().splitlines()
    if not lines:
        return "Untitled", ""
    title = lines[0].strip() or "Untitled"
    rest = "\n".join(lines[1:]).strip()
    return title, rest


def _render_block3_with_checklist(rest, asset_id, turn_idx):
    step_idx = 0
    for line in str(rest or "").splitlines():
        step = line.strip()
        if re.match(r"^\s*\d+\.", line):
            digest = hashlib.sha1(step.encode()).hexdigest()[:8]
            key = f"iso_{asset_id}_{turn_idx}_{step_idx}_{digest}"
            st.checkbox(step, key=key)
            step_idx += 1
        elif step:
            st.markdown(line)


def five_block_answer(md, asset_id, turn_idx):
    text = str(md or "")
    parts = re.split(r"(?m)^###\s+([1-5])\.\s*", text)
    if len(parts) == 1:
        st.markdown(text)
        return

    preamble = parts[0].strip()
    if preamble:
        st.markdown(preamble)

    for pos in range(1, len(parts) - 1, 2):
        n = int(parts[pos])
        title, rest = _split_block(parts[pos + 1])
        icon, expanded = BLOCK_META.get(n, ("", False))
        with st.expander(f"{icon} {n}. {title.strip()}", expanded=expanded):
            if n == 3:
                _render_block3_with_checklist(rest, asset_id, turn_idx)
            elif rest:
                st.markdown(rest)


def candidate_chips(turn, idx, on_pick):
    trace = turn.get("trace") or []
    candidates = []
    for step in trace:
        if step.get("tool") != "resolve_asset":
            continue
        output = step.get("output") or {}
        if isinstance(output, dict):
            candidates = output.get("candidates") or []
        elif isinstance(output, list):
            candidates = output
        break

    for candidate in candidates:
        asset_id = _row_value(candidate, "asset_id", default="")
        if not asset_id:
            continue
        name = _row_value(candidate, "name", default="Unknown asset")
        if st.button(f"{asset_id} — {name}", key=f"cand_{idx}_{asset_id}", use_container_width=True):
            on_pick(idx, asset_id)


def _render_alert_controls(turn, idx, on_dispatch):
    structured = turn.get("structured") or {}
    if not structured.get("alert_recommended"):
        return

    result = turn.get("alert_result")
    if result is None:
        st.warning("Alert recommended. Confirm dispatch before sending notifications.")
        confirmed = st.checkbox("I confirm this alert should be dispatched", key=f"alert_confirm_{idx}")
        if st.button("Dispatch alert", key=f"alert_dispatch_{idx}", disabled=not confirmed):
            on_dispatch(idx)
        return

    dispatched = bool(result.get("dispatched")) or result.get("status") == "dispatched"
    deduped = bool(result.get("deduped")) or result.get("status") == "deduped"
    if dispatched:
        recipients = result.get("recipients") or result.get("to") or []
        if isinstance(recipients, str):
            recipients_text = recipients
        else:
            recipients_text = ", ".join(str(r) for r in recipients)
        ts = result.get("ts") or result.get("timestamp") or "unknown time"
        st.success(f"Alert dispatched to {recipients_text or 'configured recipients'} at {ts}.")
    elif deduped:
        st.info("Duplicate alert muted; prior dispatch is still active.")
    else:
        st.info("Alert dispatch result recorded.")


def render_assistant_turn(turn, idx, on_pick, on_dispatch):
    content = turn.get("content", "")
    if turn.get("fell_back"):
        st.markdown(TH.mode_badge(turn.get("mode", "deterministic"), fell_back=True), unsafe_allow_html=True)
        first_line = content.splitlines()[0] if content.splitlines() else ""
        match = re.search(r"> \(LLM mode failed: (\w+)", first_line)
        if match:
            st.caption(f"LLM mode failed: {match.group(1)}")

    five_block_answer(content, turn.get("asset_id"), idx)

    citations = turn.get("citations") or []
    if citations:
        with st.expander("Citations", expanded=False):
            for cite in citations:
                cited_text = _row_value(cite, "cited_text", "text", default="")
                source = _row_value(cite, "source", "title", default="source")
                title = _row_value(cite, "title", default=source)
                st.markdown(f"- **{title}** ({source}): {cited_text}")

    trace = turn.get("trace") or []
    mode = turn.get("mode", "deterministic")
    with st.expander(f"🧠 How I got this — {len(trace)} tool calls · mode={mode}", expanded=False):
        for step in trace:
            tool = step.get("tool", "tool")
            payload = step.get("input", {})
            output = step.get("output", {})
            st.markdown(f"**{tool}** `{_json_inline(payload)}`")
            st.json(_jsonable(output), expanded=False)
            if isinstance(output, dict) and output.get("sql"):
                st.code(output["sql"], language="sql")

    if turn.get("pending_query"):
        candidate_chips(turn, idx, on_pick)

    _render_alert_controls(turn, idx, on_dispatch)
