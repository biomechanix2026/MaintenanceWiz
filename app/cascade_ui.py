"""Pure formatting helpers for cascade/planner Streamlit surfaces.

No Streamlit imports here: these helpers stay unit-testable and keep the app
module focused on layout.
"""
from __future__ import annotations

from app import theme as TH


def _dot_escape(value) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _band_color(band: str | None) -> str:
    token = TH.BAND_TOKENS.get(str(band or "").upper())
    return token["color"] if token else "#2E3440"


def build_topology_dot(rows: list[dict], graph: dict[str, list[str]]) -> str:
    """Return a Graphviz DOT string for the plant topology.

    Node color follows current priority band; label includes system priority so
    the visual explains why upstream bottlenecks matter without changing the
    existing priority ranking.
    """
    by_asset = {str(row.get("asset_id")): row for row in rows if row.get("asset_id")}
    node_ids = set(by_asset)
    for src, dsts in (graph or {}).items():
        node_ids.add(str(src))
        node_ids.update(str(dst) for dst in dsts)

    lines = [
        "digraph plant_topology {",
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.2", nodesep="0.5", ranksep="0.7"];',
        '  node [shape=box, style="rounded,filled", color="#2A2E35", penwidth=1.4, fontname="IBM Plex Sans"];',
        '  edge [color="#9AA3AD", arrowsize=0.7, penwidth=1.2];',
    ]

    for aid in sorted(node_ids):
        row = by_asset.get(aid, {})
        name = row.get("name") or aid
        sysp = _num(row.get("system_priority", row.get("priority_score", 0.0)))
        # Escape each label line, THEN join with the DOT newline (\n). Joining
        # first and re-escaping would double the backslash, so Graphviz would
        # render a literal "\n" and balloon the SVG width.
        label = "\\n".join((
            _dot_escape(aid),
            _dot_escape(str(name)[:24]),
            f"sys {sysp:.1f}",
        ))
        color = _band_color(row.get("band") or row.get("priority_band"))
        font = "#121417" if color not in {"#2E3440", "#242932"} else "#E8EAED"
        lines.append(
            f'  "{_dot_escape(aid)}" [label="{label}", '
            f'fillcolor="{color}", fontcolor="{font}"];'
        )

    for src in sorted(graph or {}):
        for dst in sorted(graph[src]):
            lines.append(f'  "{_dot_escape(src)}" -> "{_dot_escape(dst)}";')

    lines.append("}")
    return "\n".join(lines)


def capacity_summary(capacity: dict) -> str:
    by_skill = (capacity or {}).get("by_skill") or {}
    parts = []
    for skill in sorted(by_skill):
        row = by_skill[skill]
        used = _num(row.get("used"))
        total = _num(row.get("total"))
        left = _num(row.get("left"))
        parts.append(f"{skill} {used:.1f}/{total:.1f}h used ({left:.1f}h left)")
    return " | ".join(parts) if parts else "No crew capacity returned"


def plan_bucket_rows(plan: dict, bucket: str) -> list[dict]:
    rows = []
    for item in (plan or {}).get(bucket, []) or []:
        if bucket == "scheduled":
            rows.append({
                "Asset": item.get("asset_id"),
                "Task": item.get("task"),
                "Crew": item.get("crew_id"),
                "Hours": _num(item.get("est_hours")),
                "System Priority": _num(item.get("system_priority")),
            })
        else:
            rows.append({
                "Asset": item.get("asset_id"),
                "Reason": item.get("reason"),
                "System Priority": _num(item.get("system_priority")),
            })
    return rows
