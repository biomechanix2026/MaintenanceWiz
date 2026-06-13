"""
Next-shift planner - pure greedy allocation core.

Turns the flagged-work list into an allocated next-shift plan under two real
constraints of maintenance ops:

  1. Finite crew-hours, tracked PER CREW (not as a per-skill aggregate pool):
     a 5h job needs a single crew with 5h free, even if two 3h crews look
     sufficient in aggregate. Tracking only the skill total would silently
     overbook one crew.
  2. Spare-part feasibility: an out-of-stock long-lead part (constraint_flag)
     cannot be replaced this shift, so the asset diverts to monitored
     degradation + procurement instead of consuming crew hours.

Work is ranked by system_priority so an upstream bottleneck (cascade-boosted)
outranks an isolated asset of similar own priority.

Pure: no import of agent.tools (shift_plan_tool there composes this with the
live tools), so this stays an individually-testable unit.

Spec: docs/superpowers/plans/2026-06-13-next-shift-planner-mvp.md
"""
from __future__ import annotations


def plan_shift(candidates: list[dict], crew: list[dict], templates: dict) -> dict:
    """Greedy next-shift allocation.

    candidates: [{asset_id, asset_type, system_priority, rul_days, criticality,
                  priority_band, constraint_flag}]
    crew:       [{crew_id, skill, shift_hours}]
    templates:  {asset_type: {task, est_hours, required_skill}}
    """
    # per-crew remaining hours, and the crews available for each skill
    remaining = {c["crew_id"]: float(c["shift_hours"]) for c in crew}
    crews_by_skill: dict[str, list[str]] = {}
    for c in crew:
        crews_by_skill.setdefault(c["skill"], []).append(c["crew_id"])

    ranked = sorted(candidates,
                    key=lambda c: (-c["system_priority"], c["rul_days"], -c["criticality"]))

    scheduled: list[dict] = []
    deferred: list[dict] = []
    procurement: list[dict] = []

    for cand in ranked:
        sysp = cand["system_priority"]
        tmpl = templates.get(cand["asset_type"])
        if tmpl is None:
            deferred.append({"asset_id": cand["asset_id"], "system_priority": sysp,
                             "reason": f"no job template for type {cand['asset_type']}"})
            continue
        # spares-infeasible: the replacement cannot complete this shift
        if cand.get("constraint_flag"):
            procurement.append({"asset_id": cand["asset_id"], "system_priority": sysp,
                                "reason": cand["constraint_flag"]})
            continue
        skill = tmpl["required_skill"]
        need = float(tmpl["est_hours"])
        crews = crews_by_skill.get(skill, [])
        # best-fit: the crew of this skill with the most remaining hours
        best = max(crews, key=lambda cid: remaining[cid], default=None)
        if best is not None and remaining[best] >= need:
            remaining[best] -= need
            scheduled.append({"asset_id": cand["asset_id"], "task": tmpl["task"],
                              "crew_id": best, "est_hours": need, "system_priority": sysp})
        else:
            max_free = round(remaining[best], 1) if best is not None else 0.0
            deferred.append({"asset_id": cand["asset_id"], "system_priority": sysp,
                             "reason": f"no {skill} crew has {need}h free (max free {max_free}h)"})

    by_crew: dict[str, dict] = {}
    for c in crew:
        total = float(c["shift_hours"])
        left = remaining[c["crew_id"]]
        by_crew[c["crew_id"]] = {"total": total, "used": round(total - left, 2),
                                 "left": round(left, 2)}
    by_skill: dict[str, dict] = {}
    for skill, cids in crews_by_skill.items():
        total = sum(by_crew[cid]["total"] for cid in cids)
        used = sum(by_crew[cid]["used"] for cid in cids)
        by_skill[skill] = {"total": round(total, 2), "used": round(used, 2),
                           "left": round(total - used, 2)}

    return {"scheduled": scheduled, "deferred": deferred, "procurement": procurement,
            "capacity": {"by_crew": by_crew, "by_skill": by_skill},
            "basis": "greedy by system_priority under per-crew-hour + spares constraints"}
