"""
Graph Validator and Diagnostics for LangGraph code generator.
Validates:
- No Start edge
- Node unreachable from START
- No path to END
- Conditional edge without path map
- Cycle without a conditional exit (warning)
- State field name collision
- Missing credentials
"""

from typing import Any
from pydantic import BaseModel


class Diagnostic(BaseModel):
    level: str  # "error" | "warning" | "info"
    node_id: str | None = None
    message: str


def validate_graph(graph_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Validates a Graph JSON structure and returns a list of diagnostic dicts:
    [{"level": "error"|"warning"|"info", "node_id": str|None, "message": str}]
    """
    diagnostics: list[Diagnostic] = []

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    state = graph_data.get("state", {})
    state_fields = state.get("fields", []) if isinstance(state, dict) else []

    node_ids = {n["id"] for n in nodes if "id" in n}

    # 1. State field name collision check
    field_names: set[str] = set()
    for f in state_fields:
        name = f.get("name") if isinstance(f, dict) else str(f)
        if name in field_names:
            diagnostics.append(
                Diagnostic(
                    level="error",
                    node_id=None,
                    message=f"State field name collision: duplicate field '{name}'.",
                )
            )
        field_names.add(name)

    # 2. Check edges from START
    start_edges = [
        e for e in edges
        if e.get("source") in ("START", "__start__") or e.get("source") not in node_ids
    ]
    # In LangGraph, START is either an explicit edge source="START", or the trigger node connects to first node
    has_start_edge = False
    for e in edges:
        src = e.get("source")
        if src in ("START", "__start__"):
            has_start_edge = True
            break
        # Or if node is trigger type
        src_node = next((n for n in nodes if n.get("id") == src), None)
        if src_node and src_node.get("type") in ("trigger", "triggers"):
            has_start_edge = True
            break

    if not has_start_edge and nodes:
        diagnostics.append(
            Diagnostic(
                level="error",
                node_id=None,
                message="Graph has no edge from START or Trigger node.",
            )
        )

    # Build adjacency graphs for reachability
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    adj["START"] = []
    rev_adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    rev_adj["END"] = []

    for e in edges:
        src = "START" if e.get("source") in ("START", "__start__") else e.get("source")
        tgt = "END" if e.get("target") in ("END", "__end__") else e.get("target")

        # Conditional edge check
        if e.get("kind") == "conditional":
            cond = e.get("condition") or {}
            branches = cond.get("branches") or cond.get("path_map") or cond.get("mapping")
            if not branches:
                diagnostics.append(
                    Diagnostic(
                        level="error",
                        node_id=src if src != "START" else None,
                        message=f"Conditional edge '{e.get('id', '')}' has no path map / branches defined.",
                    )
                )
            else:
                for b_tgt in branches.values():
                    b_norm = "END" if b_tgt in ("END", "__end__") else b_tgt
                    if src in adj and b_norm:
                        adj[src].append(b_norm)
                    if b_norm in rev_adj and src:
                        rev_adj[b_norm].append(src)

        if src in adj and tgt:
            adj[src].append(tgt)
        if tgt in rev_adj and src:
            rev_adj[tgt].append(src)

    # Inspect nodes for Command/Map dynamic routing targets
    for n in nodes:
        nid = n.get("id")
        cfg = n.get("config") or {}
        targets: list[str] = []
        if cfg.get("is_command") or "command" in n.get("type", "").lower():
            for key in ("goto", "goto_true", "goto_false"):
                val = cfg.get(key)
                if isinstance(val, str):
                    targets.append(val)
                elif isinstance(val, list):
                    targets.extend(val)
            for d in cfg.get("destinations", []):
                if isinstance(d, str):
                    targets.append(d)
        if cfg.get("is_map") or "map" in n.get("type", "").lower() or cfg.get("send_target"):
            val = cfg.get("send_target") or cfg.get("target")
            if isinstance(val, str):
                targets.append(val)
            elif isinstance(val, list):
                targets.extend(val)

        for tgt in targets:
            tgt_norm = "END" if tgt in ("END", "__end__") else tgt
            if nid in adj and tgt_norm:
                adj[nid].append(tgt_norm)
            if tgt_norm in rev_adj and nid:
                rev_adj[tgt_norm].append(nid)

    # 3. Check reachability from START
    reachable_from_start: set[str] = set()
    queue = ["START"]
    # Also add triggers to queue
    for n in nodes:
        if n.get("type") in ("trigger", "triggers"):
            queue.append(n["id"])

    visited: set[str] = set()
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        reachable_from_start.add(curr)
        for neighbor in adj.get(curr, []):
            if neighbor not in visited:
                queue.append(neighbor)

    for n in nodes:
        nid = n.get("id")
        if nid and nid not in reachable_from_start:
            diagnostics.append(
                Diagnostic(
                    level="error",
                    node_id=nid,
                    message=f"Node '{n.get('label') or nid}' is unreachable from START.",
                )
            )

    # 4. Check path to END
    can_reach_end: set[str] = set()
    r_queue = ["END"]
    r_visited: set[str] = set()
    while r_queue:
        curr = r_queue.pop(0)
        if curr in r_visited:
            continue
        r_visited.add(curr)
        can_reach_end.add(curr)
        for prev in rev_adj.get(curr, []):
            if prev not in r_visited:
                r_queue.append(prev)

    for n in nodes:
        nid = n.get("id")
        # Output nodes are by definition terminal
        if n.get("type") in ("output", "end"):
            continue
        if nid and nid not in can_reach_end and nid in reachable_from_start:
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    node_id=nid,
                    message=f"Node '{n.get('label') or nid}' has no path to END.",
                )
            )

    # 5. Cycle without conditional exit check
    # Check if there is a cycle where all edges are normal (no conditional edge to break)
    def find_cycles(node: str, path: list[str], visited_cycles: set[str]):
        if node in path:
            cycle = path[path.index(node):]
            # Check if cycle has any conditional edge
            has_conditional = False
            for i in range(len(cycle)):
                s = cycle[i]
                t = cycle[(i + 1) % len(cycle)]
                for e in edges:
                    if e.get("source") == s and e.get("target") == t and e.get("kind") == "conditional":
                        has_conditional = True
                        break
                if has_conditional:
                    break
            if not has_conditional:
                cycle_str = " -> ".join(cycle + [node])
                if cycle_str not in visited_cycles:
                    visited_cycles.add(cycle_str)
                    diagnostics.append(
                        Diagnostic(
                            level="warning",
                            node_id=node,
                            message=f"Potential infinite loop: cycle ({cycle_str}) has no conditional exit.",
                        )
                    )
            return

        for neighbor in adj.get(node, []):
            if neighbor not in ("START", "END"):
                find_cycles(neighbor, path + [node], visited_cycles)

    visited_cycles: set[str] = set()
    for nid in reachable_from_start:
        if nid not in ("START", "END"):
            find_cycles(nid, [], visited_cycles)

    # 6. Check missing credentials for LLM nodes
    for n in nodes:
        cat = n.get("type", "")
        cfg = n.get("config", {})
        if cat in ("model", "models", "agent", "agents"):
            provider = (cfg.get("llmProvider") or cfg.get("provider") or "").lower()
            if provider in ("openai", "anthropic"):
                apiKey = cfg.get("apiKey") or cfg.get("api_key")
                # Missing credential warning if neither hardcoded nor env var mentioned
                if not apiKey and not cfg.get("useEnvVar", True):
                    diagnostics.append(
                        Diagnostic(
                            level="warning",
                            node_id=n.get("id"),
                            message=f"Node '{n.get('label') or n.get('id')}' uses {provider} but no API key is specified.",
                        )
                    )

    return [d.model_dump() for d in diagnostics]
