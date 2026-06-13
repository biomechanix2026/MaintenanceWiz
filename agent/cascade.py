"""
Plant cascade / bottleneck graph - pure graph core.

Builds the asset-interdependency DAG from the config-owned topology spec and
computes each asset's blast radius: the criticality-weighted, hop-decayed mass
of equipment downstream of it. Deliberately does NOT import agent.tools
(cascade_tool there is the only place own-priority and the graph meet), so this
module stays a pure, individually-testable unit.

Spec: docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md
"""
from __future__ import annotations
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def build_graph() -> dict[str, list[str]]:
    """Adjacency map from the config topology. Missing spec -> empty graph
    (feature degrades gracefully: every asset terminal)."""
    g: dict[str, list[str]] = {}

    def add(src: str, dst: str):
        if dst not in g.setdefault(src, []):
            g[src].append(dst)
        g.setdefault(dst, [])

    order_map = getattr(C, "LINE_ASSET_ORDER", {})
    # 1. intra-line serial chains
    for order in order_map.values():
        for a, b in zip(order, order[1:]):
            add(a, b)
    # 2. consecutive-line bridges (last of line k -> first of line k+1)
    flow = getattr(C, "LINE_FLOW", [])
    for k in range(len(flow) - 1):
        src_line = order_map.get(flow[k], [])
        dst_line = order_map.get(flow[k + 1], [])
        if src_line and dst_line:
            add(src_line[-1], dst_line[0])
    # 3. authored cross-line utility edges
    for src, dsts in getattr(C, "UTILITY_EDGES", {}).items():
        for d in dsts:
            add(src, d)
    return g


def downstream(asset_id: str) -> list[tuple[str, int]]:
    """Directed BFS from asset_id: [(downstream_asset, hops)] in BFS order.
    The visited set is a defensive guard - the topology is a DAG by
    construction, but an authored cycle must not hang the agent."""
    g = build_graph()
    seen = {asset_id}
    out: list[tuple[str, int]] = []
    frontier = [(asset_id, 0)]
    while frontier:
        node, hops = frontier.pop(0)
        for nxt in g.get(node, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            out.append((nxt, hops + 1))
            frontier.append((nxt, hops + 1))
    return out


def blast_radius(asset_id: str) -> tuple[float, list[dict]]:
    """Blast = sum over downstream d of criticality(d) * CASCADE_DECAY^hops(d).
    Returns (score, path detail ordered by hops then criticality desc)."""
    reg = pd.read_csv(C.ASSET_REGISTRY_CSV)
    meta = {r["asset_id"]: (r["name"], int(r["criticality"])) for _, r in reg.iterrows()}
    blast = 0.0
    path: list[dict] = []
    for aid, hops in downstream(asset_id):
        name, crit = meta.get(aid, (aid, 0))
        blast += crit * (C.CASCADE_DECAY ** hops)
        path.append({"asset_id": aid, "name": name, "hops": hops, "criticality": crit})
    path.sort(key=lambda d: (d["hops"], -d["criticality"]))
    return round(blast, 4), path


if __name__ == "__main__":
    g = build_graph()
    print(f"{len(g)} nodes, {sum(len(v) for v in g.values())} edges")
    for aid in ("GEARBOX-05", "CONV-BELT-03", "ROLL-MILL-11"):
        b, p = blast_radius(aid)
        print(f"{aid}: blast={b}  downstream={[d['asset_id'] for d in p]}")
