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
from agent.tools import (risk_score_tool, prognostic_tool, inventory_tool,
                         alert_dispatch_tool)
from config import ALERT_THRESHOLD

REPORTS_DIR = os.path.join(C.ROOT, "reports")


def run():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    reg = pd.read_csv(C.ASSET_REGISTRY_CSV)
    results = [risk_score_tool(a) for a in reg.asset_id]
    results.sort(key=lambda r: -r["priority_score"])

    crit = [r for r in results if r["priority_band"] == "CRITICAL"]
    high = [r for r in results if r["priority_band"] == "HIGH"]
    flagged = [r for r in results if r.get("constraint_flag")]

    ts = datetime.now()
    lines = [
        f"# Pre-Shift Maintenance Briefing",
        f"*Generated autonomously at {ts:%Y-%m-%d %H:%M} — before shift start.*",
        "",
        f"**{len(crit)} critical · {len(high)} high · {len(flagged)} constraint-flagged** "
        f"out of {len(results)} assets.",
        "",
        "## Action queue (drafted work orders)",
    ]

    for r in crit + high:
        aid = r["asset_id"]
        prog = prognostic_tool(aid)
        inv = inventory_tool(aid)
        out = [p for p in inv["parts"] if p["qty_on_hand"] == 0]
        name = reg[reg.asset_id == aid].iloc[0]["name"]
        lines += [
            f"### [{r['priority_band']}] {aid} — {name}",
            f"- Priority **{r['priority_score']}/100**, RUL **{r['rul_days']}d**, "
            f"top driver **{prog['shap']['top_driver']}**.",
            f"- Drafted WO: inspect/repair per SOP-{aid}; "
            + ("**order now** (long lead): "
               + ", ".join(f"{p['part_no']} ({p['lead_time_days']}d)" for p in out) + "."
               if out else "required parts in stock."),
        ]
        if r.get("constraint_flag"):
            lines.append(f"- ⚠️ {r['constraint_flag']}")
            # auto-dispatch alert for critical/constrained
        if r["priority_score"] >= ALERT_THRESHOLD:
            alert_dispatch_tool(aid, r["priority_band"],
                                f"Pre-shift: {aid} {r['priority_band']} score {r['priority_score']}, "
                                f"RUL {r['rul_days']}d.")
            lines.append("- 📧 Alert dispatched to maintenance team.")
        lines.append("")

    path = os.path.join(REPORTS_DIR, f"preshift_{ts:%Y%m%d_%H%M}.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Pre-shift briefing written: {path}")
    print(f"  {len(crit)} critical, {len(high)} high, {len(flagged)} constraint-flagged.")
    return path


if __name__ == "__main__":
    run()
