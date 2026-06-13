"""
Pre-shift autonomous run (System of Action).

Runs the full diagnostic pipeline across every asset BEFORE anyone logs in,
drafts work orders for everything that needs attention, dispatches alerts for
CRITICAL assets, and writes a timestamped markdown briefing. Designed to be
scheduled (cron / Task Scheduler) so the morning shift walks in to a prepared
plan rather than a blank screen.

Run:  python -m scripts.pre_shift_run
Cron: 0 6 * * *  cd /path/to/MaintenanceWiz_1 && python -m scripts.pre_shift_run
"""
from __future__ import annotations
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from agent.tools import (risk_score_tool, prognostic_tool, abnormality_tool,
                         inventory_tool, alert_dispatch_tool, shift_plan_tool,
                         work_order_draft_tool)
from config import ALERT_THRESHOLD

REPORTS_DIR = os.path.join(C.ROOT, "reports")


def run():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    reg = pd.read_csv(C.ASSET_REGISTRY_CSV)
    results = []
    for aid in reg.asset_id:
        r = risk_score_tool(aid)
        abn = abnormality_tool(aid)
        r["abnormality"] = abn
        r["anomaly_status"] = abn["status"]
        r["anomaly_score"] = abn["anomaly_score"]
        results.append(r)
    results.sort(key=lambda r: (-r["priority_score"], -r["anomaly_score"]))

    crit = [r for r in results if r["priority_band"] == "CRITICAL"]
    high = [r for r in results if r["priority_band"] == "HIGH"]
    flagged = [r for r in results if r.get("constraint_flag")]
    abnormal = [r for r in results if r["anomaly_status"] != "NORMAL"]
    action_queue = [r for r in results
                    if r["priority_band"] in ("CRITICAL", "HIGH")
                    or r["anomaly_status"] != "NORMAL"
                    or r.get("constraint_flag")]   # constraint-only assets are the
                                                   # differentiated behaviour - include them

    ts = datetime.now()
    lines = [
        f"# Pre-Shift Maintenance Briefing",
        f"*Generated autonomously at {ts:%Y-%m-%d %H:%M} — before shift start.*",
        "",
        f"**{len(crit)} critical · {len(high)} high · {len(abnormal)} abnormal · "
        f"{len(flagged)} constraint-flagged** "
        f"out of {len(results)} assets.",
        "",
        "## Action queue (drafted work orders)",
    ]

    for r in action_queue:
        aid = r["asset_id"]
        prog = prognostic_tool(aid)
        inv = inventory_tool(aid)
        out = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
        name = reg[reg.asset_id == aid].iloc[0]["name"]
        lines += [
            f"### [{r['priority_band']}] {aid} — {name}",
            f"- Priority **{r['priority_score']}/100**, RUL **{r['rul_days']}d**, "
            f"top driver **{prog['shap']['top_driver']}**.",
            f"- Independent abnormality: **{r['anomaly_status']}** "
            f"({r['anomaly_score']}/100). {r['abnormality']['recommendation']}",
            f"- Drafted WO: inspect/repair per SOP-{aid}; "
            + ("**order now** (long lead): "
               + ", ".join(f"{p['part_no']} ({p['lead_time_days']}d)" for p in out) + "."
               if out else "required parts in stock."),
        ]
        if r.get("constraint_flag"):
            lines.append(f"- ⚠️ {r['constraint_flag']}")
            # auto-dispatch alert for critical/constrained
        if r["priority_score"] >= ALERT_THRESHOLD or r["abnormality"].get("catastrophic_risk"):
            level = r["priority_band"] if r["priority_score"] >= ALERT_THRESHOLD else "ANOMALY-CRITICAL"
            alert_dispatch_tool(aid, level,
                                f"Pre-shift: {aid} {level} score {r['priority_score']}, "
                                f"RUL {r['rul_days']}d, anomaly {r['anomaly_status']}.")
            lines.append("- 📧 Alert dispatched to maintenance team.")
        lines.append("")

    # Next-shift plan: allocate the flagged work to crews under crew-hour +
    # spares constraints. Turns the action queue from a list into an allocated
    # plan (the operating-process payoff).
    plan = shift_plan_tool()
    cap = ", ".join(f"{sk} {c['used']}/{c['total']}h"
                    for sk, c in plan["capacity"]["by_skill"].items())
    lines += ["## Next shift plan",
              f"*{plan['candidate_count']} flagged asset(s); crew-hours allocated by system priority "
              f"(utilisation: {cap}).*", ""]
    if plan["scheduled"]:
        lines.append("**Scheduled this shift:**")
        lines += [f"- {s['asset_id']} — {s['task']} → {s['crew_id']} "
                  f"({s['est_hours']}h, sys priority {s['system_priority']})"
                  for s in plan["scheduled"]]
    if plan["deferred"]:
        lines += ["", "**Deferred (capacity):**"]
        lines += [f"- {d['asset_id']} — {d['reason']}" for d in plan["deferred"]]
    if plan["procurement"]:
        lines += ["", "**Procurement / monitored degradation (part infeasible this shift):**"]
        lines += [f"- {p['asset_id']} — {p['reason']}" for p in plan["procurement"]]
    lines.append("")

    # Draft trace-backed work orders for the scheduled jobs (system of action).
    # Persist under the report dir so a scheduled run leaves draft WO artifacts;
    # approval-gated (DRAFT only, no autonomous closure).
    wo = work_order_draft_tool(persist=True, out_dir=os.path.join(REPORTS_DIR, "work_orders"))
    lines += ["## Drafted work orders (CMMS - draft, approval-gated)",
              f"*{wo['count']} draft WO(s) written to reports/work_orders/; "
              f"each carries risk + cascade + SOP + spares + crew evidence.*", ""]
    lines += [f"- `{w['work_order_id']}` — {w['asset_id']} {w['task']} → {w['crew_id']} "
              f"({w['planned_hours']}h); SOP: {', '.join(w['evidence']['sop_citations'][:1]) or 'n/a'}"
              for w in wo["work_orders"]]
    lines.append("")

    path = os.path.join(REPORTS_DIR, f"preshift_{ts:%Y%m%d_%H%M}.md")
    with open(path, "w", encoding="utf-8") as f:  # report contains non-ASCII (⚠️/📧)
        f.write("\n".join(lines))
    print(f"Pre-shift briefing written: {path}")
    print(f"  {len(crit)} critical, {len(high)} high, {len(abnormal)} abnormal, "
          f"{len(flagged)} constraint-flagged.")
    return path


if __name__ == "__main__":
    run()
