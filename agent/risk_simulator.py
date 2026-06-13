"""
Pure seeded Independent-Cascade Monte-Carlo over a plant dependency graph.

No file IO, no pandas, no Streamlit/Anthropic/RAG. Accepts already-normalized
inputs (nodes, weighted edges, per-node spontaneous failure probs, per-node direct
event costs). Uses COMMON RANDOM NUMBERS so candidate suppression is a paired,
near-zero-variance comparison against baseline (monotone: suppressing a spontaneous
seed can only remove activations).

Edge weight is interpreted as a per-hop propagation probability, clamped to
[floor, cap]. Suppression zeroes a node's SPONTANEOUS seed only; the node remains
susceptible to upstream propagation.

Spec: docs/superpowers/specs/2026-06-13-financial-cost-engine-simulator-design.md
"""
from __future__ import annotations
import numpy as np


def _topo(nodes: list[str], edges: list[tuple]) -> list[str]:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for u, v, _w in edges:
        adj[u].append(v)
        indeg[v] += 1
    q = [n for n in nodes if indeg[n] == 0]
    order: list[str] = []
    while q:
        n = q.pop(0)
        order.append(n)
        for v in adj[n]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(order) != len(nodes):           # cycle guard: append remaining once
        order += [n for n in nodes if n not in set(order)]
    return order


def _prep(nodes, edges, edge_floor, edge_cap):
    order = _topo(nodes, edges)
    idx = {n: k for k, n in enumerate(order)}
    edge_p = (np.array([min(edge_cap, max(edge_floor, w)) for _, _, w in edges])
              if edges else np.zeros(0))
    incoming: dict[int, list[tuple[int, int]]] = {}
    for e, (u, v, _w) in enumerate(edges):
        incoming.setdefault(idx[v], []).append((e, idx[u]))
    return order, idx, incoming, edge_p


def _activations(order, idx, incoming, edge_p, seed_p, U_seed, U_edge):
    active = U_seed < seed_p                # (trials, n) spontaneous
    for v in order:                         # topo order: upstream finalized first
        i = idx[v]
        for e, ui in incoming.get(i, ()):
            active[:, i] |= active[:, ui] & (U_edge[:, e] < edge_p[e])
    return active


def _draws(order, edges, seed, trials):
    rng = np.random.default_rng(seed)
    U_seed = rng.random((trials, len(order)))
    U_edge = rng.random((trials, len(edges))) if edges else np.zeros((trials, 0))
    return U_seed, U_edge


def simulate_plant_risk(nodes, edges, seed_probs, node_cost, *, trials, seed,
                        edge_floor=0.05, edge_cap=0.85) -> dict:
    order, idx, incoming, edge_p = _prep(nodes, edges, edge_floor, edge_cap)
    U_seed, U_edge = _draws(order, edges, seed, trials)
    seed_p = np.array([seed_probs.get(n, 0.0) for n in order])
    cost = np.array([node_cost.get(n, 0.0) for n in order])
    active = _activations(order, idx, incoming, edge_p, seed_p, U_seed, U_edge)
    losses = active @ cost
    contrib = active.mean(axis=0) * cost
    contrib_map = {order[k]: round(float(contrib[k]), 2) for k in range(len(order))}
    top = sorted(
        ({"asset_id": order[k], "mean_loss_contribution_usd": round(float(contrib[k]), 2)}
         for k in range(len(order))),
        key=lambda r: r["mean_loss_contribution_usd"], reverse=True)[:5]
    return {
        "mean_eml_usd": round(float(losses.mean()), 2),
        "p50_eml_usd": round(float(np.percentile(losses, 50)), 2),
        "p90_eml_usd": round(float(np.percentile(losses, 90)), 2),
        "p95_eml_usd": round(float(np.percentile(losses, 95)), 2),
        "trial_count": int(trials),
        "seed": int(seed),
        "loss_contributions": contrib_map,
        "top_contributors": top,
    }


def rank_interventions(nodes, edges, seed_probs, node_cost, candidates, *,
                       trials, seed, edge_floor=0.05, edge_cap=0.85) -> list:
    """Each candidate: {asset_id, action, intervention_cost_usd, ...passthrough}.
    Only 'repair_now' suppresses spontaneous failure this shift. Actions
    'procure_for_window'/'monitor'/'defer_capacity' apply NO suppression
    (averted == 0); procurement value is reported as value-at-risk elsewhere."""
    order, idx, incoming, edge_p = _prep(nodes, edges, edge_floor, edge_cap)
    U_seed, U_edge = _draws(order, edges, seed, trials)     # common random numbers
    base_seed_p = np.array([seed_probs.get(n, 0.0) for n in order])
    cost = np.array([node_cost.get(n, 0.0) for n in order])
    base_active = _activations(order, idx, incoming, edge_p, base_seed_p, U_seed, U_edge)
    base_eml = float((base_active @ cost).mean())

    out = []
    for c in candidates:
        if c.get("action") != "repair_now" or c["asset_id"] not in idx:
            averted = 0.0
        else:
            sp = base_seed_p.copy()
            sp[idx[c["asset_id"]]] = 0.0                   # suppress spontaneous seed only
            act = _activations(order, idx, incoming, edge_p, sp, U_seed, U_edge)
            averted = base_eml - float((act @ cost).mean())
        net = averted - float(c.get("intervention_cost_usd", 0.0))
        out.append({**c,
                    "gross_averted_eml_usd": round(averted, 2),
                    "net_averted_eml_usd": round(net, 2)})
    out.sort(key=lambda r: r["net_averted_eml_usd"], reverse=True)
    return out
