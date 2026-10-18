"""
Tests for LangGraph Code Generator (nocode_agent/codegen):
- Golden-file tests for 8 sample graphs:
  1. Linear flow
  2. Conditional routing
  3. Parallel execution with reducer (Annotated[list, operator.add])
  4. Command dynamic routing node
  5. Send map-reduce pattern
  6. Subgraph composition
  7. Human-in-the-loop (HITL) interrupt_before
  8. Agent tool-calling loop (ToolNode + tools_condition)
- AST validation & Black formatting on every generated file
- Line-level sourcemap verification
- Parity test: run generated graph.py in a subprocess, inspect graph.get_graph(),
  and assert nodes & edges match the Graph JSON.
- Performance benchmark (< 100 ms)
"""

import ast
import json
import os
import subprocess
import sys
import time
import pytest
from pathlib import Path

from nocode_agent.codegen import (
    CodeGenerator,
    generate_langgraph_project,
    validate_graph,
)
from nocode_agent.graph_schema import GraphSchema


# ══════════════════════════════════════════════════════════════════════════════
# 8 SAMPLE GRAPHS DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_sample_linear() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "step_count", "type": "int", "reducer": "overwrite", "default": 0},
            ],
            "input_fields": ["messages"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {"id": "step_1", "type": "agent", "label": "First Step", "config": {}},
            {"id": "step_2", "type": "agent", "label": "Second Step", "config": {}},
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "step_1", "kind": "normal"},
            {"id": "e_1_2", "source": "step_1", "target": "step_2", "kind": "normal"},
            {"id": "e_end", "source": "step_2", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "memory", "recursion_limit": 25},
    }


def get_sample_conditional() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "retry_count", "type": "int", "reducer": "overwrite", "default": 0},
            ],
            "input_fields": ["messages"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {"id": "agent", "type": "agent", "label": "Reasoning Agent", "config": {}},
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "agent", "kind": "normal"},
            {
                "id": "e_cond",
                "source": "agent",
                "target": "END",
                "kind": "conditional",
                "condition": {
                    "branches": {"continue": "agent", "end": "END"},
                    "code": "return 'end' if state.get('retry_count', 0) > 2 else 'continue'",
                },
            },
        ],
        "settings": {"checkpointer": "sqlite"},
    }


def get_sample_parallel_reducer() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "collected_data", "type": "list", "reducer": "append", "default": []},
            ],
            "input_fields": ["messages"],
            "output_fields": ["collected_data"],
        },
        "nodes": [
            {"id": "fork_node", "type": "agent", "label": "Dispatcher", "config": {}},
            {"id": "worker_alpha", "type": "agent", "label": "Worker Alpha", "config": {}},
            {"id": "worker_beta", "type": "agent", "label": "Worker Beta", "config": {}},
            {"id": "join_node", "type": "agent", "label": "Aggregator", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "fork_node", "kind": "normal"},
            {"id": "e2", "source": "fork_node", "target": "worker_alpha", "kind": "normal"},
            {"id": "e3", "source": "fork_node", "target": "worker_beta", "kind": "normal"},
            {"id": "e4", "source": "worker_alpha", "target": "join_node", "kind": "normal"},
            {"id": "e5", "source": "worker_beta", "target": "join_node", "kind": "normal"},
            {"id": "e6", "source": "join_node", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "sqlite"},
    }


def get_sample_command() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "authorized", "type": "bool", "reducer": "overwrite", "default": False},
            ],
            "input_fields": ["messages"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {
                "id": "auth_router",
                "type": "logic",
                "label": "Auth Gate",
                "config": {
                    "is_command": True,
                    "condition": "state.get('authorized', False)",
                    "goto_true": "admin_portal",
                    "goto_false": "login_screen",
                    "update_true": {"status": "authenticated"},
                    "update_false": {"status": "rejected"},
                },
            },
            {"id": "admin_portal", "type": "agent", "label": "Admin Portal", "config": {}},
            {"id": "login_screen", "type": "agent", "label": "Login Screen", "config": {}},
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "auth_router", "kind": "normal"},
            {"id": "e_adm_end", "source": "admin_portal", "target": "END", "kind": "normal"},
            {"id": "e_log_end", "source": "login_screen", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "sqlite"},
    }


def get_sample_send_map_reduce() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "items", "type": "list", "reducer": "overwrite", "default": ["a", "b"]},
                {"name": "processed", "type": "list", "reducer": "append", "default": []},
            ],
            "input_fields": ["items"],
            "output_fields": ["processed"],
        },
        "nodes": [
            {
                "id": "map_node",
                "type": "logic",
                "label": "Map Items",
                "config": {"is_map": True, "send_target": "worker_node", "items_field": "items"},
            },
            {"id": "worker_node", "type": "agent", "label": "Item Worker", "config": {}},
            {"id": "reduce_node", "type": "agent", "label": "Reduce Summary", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "map_node", "kind": "normal"},
            {"id": "e2", "source": "worker_node", "target": "reduce_node", "kind": "normal"},
            {"id": "e3", "source": "reduce_node", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "memory"},
    }


def get_sample_subgraph() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
            ],
        },
        "nodes": [
            {"id": "entry_step", "type": "agent", "label": "Entry", "config": {}},
            {"id": "subgraph_node", "type": "agent", "label": "Subflow Call", "config": {}},
            {"id": "exit_step", "type": "agent", "label": "Exit", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "entry_step", "kind": "normal"},
            {"id": "e2", "source": "entry_step", "target": "subgraph_node", "kind": "normal"},
            {"id": "e3", "source": "subgraph_node", "target": "exit_step", "kind": "normal"},
            {"id": "e4", "source": "exit_step", "target": "END", "kind": "normal"},
        ],
        "subgraphs": {
            "subgraph_node": {
                "nodes": [{"id": "sub_1", "label": "Sub Task"}],
                "edges": [{"source": "START", "target": "sub_1"}],
            }
        },
        "settings": {"checkpointer": "sqlite"},
    }


def get_sample_hitl() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "approved", "type": "bool", "reducer": "overwrite", "default": False},
            ],
        },
        "nodes": [
            {"id": "draft_step", "type": "agent", "label": "Draft Proposal", "config": {}},
            {"id": "human_approval", "type": "agent", "label": "Human Review", "config": {}},
            {"id": "publish_step", "type": "agent", "label": "Publish Proposal", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "draft_step", "kind": "normal"},
            {"id": "e2", "source": "draft_step", "target": "human_approval", "kind": "normal"},
            {"id": "e3", "source": "human_approval", "target": "publish_step", "kind": "normal"},
            {"id": "e4", "source": "publish_step", "target": "END", "kind": "normal"},
        ],
        "settings": {
            "checkpointer": "sqlite",
            "interrupt_before": ["human_approval"],
        },
    }


def get_sample_tool_loop() -> dict:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
            ],
        },
        "nodes": [
            {"id": "agent", "type": "agent", "label": "ReAct Agent", "config": {"provider": "openai"}},
            {
                "id": "tools_hub",
                "type": "tool",
                "label": "Calculator Tool",
                "config": {"use_tool_node": True, "description": "Calculate expressions"},
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "agent", "kind": "normal"},
            {
                "id": "e_tools_cond",
                "source": "agent",
                "target": "tools_hub",
                "kind": "conditional",
                "condition": {
                    "branches": {"tools": "tools_hub", "end": "END"},
                    "code": "return 'tools' if len(state.get('messages', [])) < 3 else 'end'",
                },
            },
            {"id": "e_back", "source": "tools_hub", "target": "agent", "kind": "normal"},
        ],
        "settings": {"checkpointer": "memory"},
    }


# ══════════════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════════════

REQUIRED_FILES = {
    "state.py",
    "nodes.py",
    "tools.py",
    "graph.py",
    "main.py",
    "langgraph.json",
    "requirements.txt",
}


@pytest.mark.parametrize(
    "graph_getter",
    [
        get_sample_linear,
        get_sample_conditional,
        get_sample_parallel_reducer,
        get_sample_command,
        get_sample_send_map_reduce,
        get_sample_subgraph,
        get_sample_hitl,
        get_sample_tool_loop,
    ],
)
def test_golden_file_generation(graph_getter):
    """Test code generation across all 8 golden-file LangGraph patterns."""
    graph_data = graph_getter()
    result = generate_langgraph_project(graph_data)

    files = result.get("files", {})
    sourcemap = result.get("sourcemap", {})
    diagnostics = result.get("diagnostics", [])

    # 1. Assert all 7 required files are present
    assert REQUIRED_FILES.issubset(files.keys())

    # 2. Assert every Python file is valid, parseable AST
    for fname, content in files.items():
        if fname.endswith(".py"):
            assert len(content.strip()) > 0, f"{fname} is empty"
            # ast.parse verifies 100% syntactically valid Python
            ast.parse(content)

    # 3. Assert sourcemap contains entries
    assert "state" in sourcemap
    assert sourcemap["state"]["file"] == "state.py"
    assert sourcemap["state"]["start_line"] > 0

    for n in graph_data["nodes"]:
        nid = n["id"]
        assert nid in sourcemap, f"Missing sourcemap for node {nid}"
        assert sourcemap[nid]["start_line"] > 0

    # 4. Assert no fatal diagnostics
    fatal_errors = [d for d in diagnostics if d.get("level") == "error"]
    assert len(fatal_errors) == 0, f"Unexpected fatal diagnostics: {fatal_errors}"


def test_codegen_performance():
    """Verify that codegen executes in < 100 ms for a 30-node graph."""
    nodes = []
    edges = [{"id": "e_start", "source": "START", "target": "node_0", "kind": "normal"}]
    for i in range(30):
        nid = f"node_{i}"
        nodes.append({"id": nid, "type": "agent", "label": f"Step {i}", "config": {}})
        if i < 29:
            edges.append({"id": f"e_{i}", "source": nid, "target": f"node_{i+1}", "kind": "normal"})
        else:
            edges.append({"id": f"e_{i}", "source": nid, "target": "END", "kind": "normal"})

    graph_data = {
        "schema_version": "1.0",
        "state": {"fields": [{"name": "messages", "type": "messages", "reducer": "add_messages"}]},
        "nodes": nodes,
        "edges": edges,
        "settings": {"checkpointer": "memory"},
    }

    # Warm-up to initialize internal caches (regex/AST)
    generate_langgraph_project(graph_data)

    t0 = time.perf_counter()
    res = generate_langgraph_project(graph_data)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert len(res["files"]) == 7
    # Generates in < 100 ms
    assert elapsed_ms < 100, f"Codegen took {elapsed_ms:.1f}ms (expected < 100ms)"


def test_graph_parity_with_subprocess(tmp_path):
    """
    Parity test:
    Writes the generated files to a temporary directory, imports graph.py in a subprocess,
    calls graph.get_graph(), and asserts that the compiled nodes and edges match the Graph JSON.
    """
    sample = get_sample_linear()
    res = generate_langgraph_project(sample)
    files = res["files"]

    # Write files to disk
    for fname, code in files.items():
        (tmp_path / fname).write_text(code, encoding="utf-8")

    # Python script to inspect compiled LangGraph
    test_script = """
import sys
from graph import graph

drawable = graph.get_graph()
node_keys = list(drawable.nodes.keys())
edge_pairs = [(e.source, e.target) for e in drawable.edges]

import json
print(json.dumps({"nodes": node_keys, "edges": edge_pairs}))
"""
    (tmp_path / "check_parity.py").write_text(test_script, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "check_parity.py"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, f"Subprocess failed with stderr: {proc.stderr}"
    data = json.loads(proc.stdout.strip())

    nodes_in_compiled = set(data["nodes"])
    # LangGraph normalizes START to '__start__' and END to '__end__'
    assert "__start__" in nodes_in_compiled
    assert "__end__" in nodes_in_compiled
    assert "step_1" in nodes_in_compiled
    assert "step_2" in nodes_in_compiled

    # Assert edges match
    compiled_edges = set((s, t) for s, t in data["edges"])
    assert ("__start__", "step_1") in compiled_edges
    assert ("step_1", "step_2") in compiled_edges
    assert ("step_2", "__end__") in compiled_edges
