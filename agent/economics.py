"""
Pure direct-cost economics primitives for Maintenance Wizard.

Computes per-event and per-action dollar primitives ONLY. No pandas, no file IO,
no RAG, no inventory lookup, and NO cascade composition - cascade cost is composed
by the caller (cost_tool / risk_simulator) which holds the graph. This keeps the
core individually testable with synthetic scalars.

Spec: docs/superpowers/specs/2026-06-13-financial-cost-engine-simulator-design.md
"""
from __future__ import annotations


def direct_event_cost(*, asset_type: str,
                      downtime_min_per_event: float,
                      tonnage_lost_per_event: float,
                      downtime_cost_usd_per_hour: float,
                      tonnage_margin_usd_per_ton: float) -> dict:
    """Direct cost of ONE failure event. Inputs are PER-EVENT - callers must divide
    aggregate delay history by event count before calling. Labelled a proxy."""
    downtime_usd = (downtime_min_per_event / 60.0) * downtime_cost_usd_per_hour
    tonnage_usd = tonnage_lost_per_event * tonnage_margin_usd_per_ton
    total = downtime_usd + tonnage_usd
    return {
        "asset_type": asset_type,
        "downtime_usd": round(downtime_usd, 2),
        "tonnage_usd": round(tonnage_usd, 2),
        "total_usd": round(total, 2),
        "label": "expected event-cost proxy",
        "basis": {
            "downtime_min_per_event": downtime_min_per_event,
            "tonnage_lost_per_event": tonnage_lost_per_event,
            "downtime_cost_usd_per_hour": downtime_cost_usd_per_hour,
            "tonnage_margin_usd_per_ton": tonnage_margin_usd_per_ton,
        },
    }


def planned_action_cost(*, planned_hours: float,
                        downtime_cost_usd_per_hour: float,
                        planned_stop_cost_factor: float,
                        primary_part_unit_cost_usd: float) -> dict:
    """Cost of doing the planned job: a discounted planned stop plus the part."""
    planned_downtime_usd = planned_hours * downtime_cost_usd_per_hour * planned_stop_cost_factor
    part_usd = primary_part_unit_cost_usd
    return {
        "planned_downtime_usd": round(planned_downtime_usd, 2),
        "part_usd": round(part_usd, 2),
        "total_usd": round(planned_downtime_usd + part_usd, 2),
    }


def emv(*, p_failure: float, failure_cost_usd: float, action_cost_usd: float) -> dict:
    """Expected value preserved by acting now vs. running to failure."""
    expected_failure_loss = p_failure * failure_cost_usd
    value_preserved = expected_failure_loss - action_cost_usd
    # A zero-cost action is a monitor decision (no repair performed), so it is
    # never labelled "value preserved" however large the exposure - check first.
    if action_cost_usd == 0:
        rec = "monitor"
    elif value_preserved > 0:
        rec = "positive_expected_value"
    else:
        rec = "not_economic_on_30d_horizon"
    return {
        "expected_failure_loss_usd": round(expected_failure_loss, 2),
        "action_cost_usd": round(action_cost_usd, 2),
        "expected_value_preserved_usd": round(value_preserved, 2),
        "recommendation": rec,
    }
