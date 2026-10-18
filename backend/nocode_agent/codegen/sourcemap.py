"""
AST-based sourcemap builder for LangGraph generated files.
Maps <node_id>, state, and edge:<id> to {file, start_line, end_line}.
"""

import ast
from typing import Any


def extract_sourcemap(
    files: dict[str, str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    node_to_fn_map: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """
    Parses generated Python files using ast.parse to map:
      - 'state' -> line range of GraphState in state.py
      - '<node_id>' -> line range of node function in nodes.py (or node registration in graph.py)
      - 'edge:<id>' -> line range of edge definition in graph.py
    """
    sourcemap: dict[str, dict[str, Any]] = {}

    # 1. State mapping in state.py
    if "state.py" in files:
        try:
            tree = ast.parse(files["state.py"])
            for stmt in ast.walk(tree):
                if isinstance(stmt, ast.ClassDef) and stmt.name == "GraphState":
                    sourcemap["state"] = {
                        "file": "state.py",
                        "start_line": stmt.lineno,
                        "end_line": getattr(stmt, "end_lineno", stmt.lineno),
                    }
                    break
        except Exception:
            pass

    # 2. Node function mappings in nodes.py
    fn_to_node: dict[str, str] = {fn_name: nid for nid, fn_name in node_to_fn_map.items()}

    if "nodes.py" in files:
        try:
            tree = ast.parse(files["nodes.py"])
            for stmt in ast.walk(tree):
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    matched_node_id = fn_to_node.get(stmt.name)
                    if matched_node_id:
                        sourcemap[matched_node_id] = {
                            "file": "nodes.py",
                            "start_line": stmt.lineno,
                            "end_line": getattr(stmt, "end_lineno", stmt.lineno),
                        }
        except Exception:
            pass

    # 3. Edge mappings & fallback node registrations in graph.py
    if "graph.py" in files:
        lines = files["graph.py"].splitlines()
        for idx, line in enumerate(lines, 1):
            # Check edge marker comments: e.g. # edge:e1
            if "# edge:" in line:
                edge_id = line.split("# edge:")[1].strip().split()[0]
                sourcemap[f"edge:{edge_id}"] = {
                    "file": "graph.py",
                    "start_line": idx,
                    "end_line": idx,
                }
            # Fallback node mapping if not in nodes.py
            for n in nodes:
                nid = n.get("id")
                if nid and nid not in sourcemap:
                    if f'builder.add_node("{nid}"' in line or f'builder.add_node("{n.get("label")}"' in line:
                        sourcemap[nid] = {
                            "file": "graph.py",
                            "start_line": idx,
                            "end_line": idx,
                        }

    # Ensure all nodes have an entry
    for n in nodes:
        nid = n.get("id")
        if nid and nid not in sourcemap:
            sourcemap[nid] = {
                "file": "nodes.py" if "nodes.py" in files else "graph.py",
                "start_line": 1,
                "end_line": 1,
            }

    # Ensure all edges have an entry
    for e in edges:
        eid = e.get("id")
        key = f"edge:{eid}"
        if key not in sourcemap:
            sourcemap[key] = {
                "file": "graph.py",
                "start_line": 1,
                "end_line": 1,
            }

    return sourcemap
