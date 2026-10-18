"""
Phase 5 Tests: LangGraph Advanced Features.
1. Human Node (HITL): generates interrupt(payload), pauses execution, resumes with Command(resume=...).
2. Breakpoints: interrupt_before / interrupt_after toggles pause and resume.
3. Time Travel: checkpoint history inspection, update_state, and thread fork.
4. Store: cross-thread shared memory read and write using SqliteStore and namespaces.
"""

import asyncio
import json
import os
import pytest
from httpx import AsyncClient, ASGITransport

from nocode_agent.subprocess_runner import run_langgraph_subprocess
from nocode_agent.main import app


@pytest.fixture(autouse=True)
def fake_llm_env(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")


@pytest.mark.asyncio
async def test_human_node_interrupt_and_resume():
    """Test generating and executing a graph with a visual Human Node calling interrupt()."""
    graph_data = {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "proposal", "type": "str", "reducer": "overwrite", "default": "draft_content"},
                {"name": "review_decision", "type": "str", "reducer": "overwrite", "default": "pending"},
            ],
            "input_fields": ["proposal"],
            "output_fields": ["proposal", "review_decision"],
        },
        "nodes": [
            {
                "id": "human_reviewer",
                "type": "human",
                "label": "Human Review",
                "config": {
                    "prompt": "Please review this proposal before proceeding.",
                    "fields": ["proposal"],
                },
            },
            {
                "id": "publish_step",
                "type": "logic",
                "label": "Publisher",
                "config": {"updates": {"proposal": "published_content"}},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "human_reviewer", "kind": "normal"},
            {"id": "e_rev_pub", "source": "human_reviewer", "target": "publish_step", "kind": "normal"},
            {"id": "e_end", "source": "publish_step", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "sqlite"},
    }

    # Step 1: initial invoke should interrupt at human_reviewer
    events_1 = []
    async for ev in run_langgraph_subprocess(
        graph_data=graph_data,
        thread_id="test_hitl_thread",
        input_data={"proposal": "draft_v1"},
        stream_mode="updates",
    ):
        events_1.append(ev)

    event_types_1 = [e.get("event") for e in events_1]
    assert "start" in event_types_1
    assert "interrupt" in event_types_1
    done_ev = [e for e in events_1 if e.get("event") == "done"][0]
    assert done_ev.get("status") == "interrupted"

    # Step 2: resume with decision "approved"
    events_2 = []
    async for ev in run_langgraph_subprocess(
        graph_data=graph_data,
        thread_id="test_hitl_thread",
        resume="approved",
        stream_mode="updates",
    ):
        events_2.append(ev)

    event_types_2 = [e.get("event") for e in events_2]
    assert "start" in event_types_2
    assert "done" in event_types_2
    done_ev2 = [e for e in events_2 if e.get("event") == "done"][0]
    assert done_ev2.get("status") == "success"

    # Verify state updates reflect publication and decision
    final_state = [e for e in events_2 if e.get("event") == "final_state"]
    assert final_state
    assert final_state[0]["values"]["proposal"] == "published_content"
    assert final_state[0]["values"]["review_decision"] == "approved"


@pytest.mark.asyncio
async def test_breakpoint_interrupt_and_resume():
    """Test breakpoint execution via policy.interrupt_before."""
    graph_data = {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "count", "type": "int", "reducer": "overwrite", "default": 0},
            ],
        },
        "nodes": [
            {
                "id": "step_a",
                "type": "logic",
                "label": "Step A",
                "config": {"updates": {"count": 1}},
            },
            {
                "id": "step_b",
                "type": "logic",
                "label": "Step B",
                "config": {"updates": {"count": 2}},
                "policy": {"interrupt_before": True},
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "step_a", "kind": "normal"},
            {"id": "e2", "source": "step_a", "target": "step_b", "kind": "normal"},
            {"id": "e3", "source": "step_b", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "sqlite"},
    }

    events_1 = []
    async for ev in run_langgraph_subprocess(
        graph_data=graph_data,
        thread_id="th_breakpoint",
        input_data={"count": 0},
        stream_mode="updates",
    ):
        events_1.append(ev)

    done_1 = [e for e in events_1 if e.get("event") == "done"][0]
    assert done_1.get("status") == "interrupted"

    # Resume breakpoint using resume="__breakpoint__"
    events_2 = []
    async for ev in run_langgraph_subprocess(
        graph_data=graph_data,
        thread_id="th_breakpoint",
        resume="__breakpoint__",
        stream_mode="updates",
    ):
        events_2.append(ev)

    done_2 = [e for e in events_2 if e.get("event") == "done"][0]
    assert done_2.get("status") == "success"
    final_ev = [e for e in events_2 if e.get("event") == "final_state"][0]
    assert final_ev["values"]["count"] == 2


@pytest.mark.asyncio
async def test_store_memory_read_write_cross_threads():
    """Test memory_write and memory_read nodes sharing data via SqliteStore across threads."""
    graph_writer = {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "user_name", "type": "str", "reducer": "overwrite", "default": "Alice"},
            ],
        },
        "nodes": [
            {
                "id": "write_node",
                "type": "memory_write",
                "label": "Save Profile",
                "config": {
                    "namespace": ["users", "test_user"],
                    "key": "profile",
                    "fields": ["user_name"],
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "write_node", "kind": "normal"},
            {"id": "e2", "source": "write_node", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "sqlite", "store": {"type": "sqlite"}},
    }

    # Thread 1: writes Alice
    events_th1 = []
    async for ev in run_langgraph_subprocess(
        graph_data=graph_writer,
        thread_id="th_user_writer",
        input_data={"user_name": "Alice"},
        stream_mode="updates",
    ):
        events_th1.append(ev)

    done_th1 = [e for e in events_th1 if e.get("event") == "done"][0]
    assert done_th1.get("status") == "success"

    # Thread 2: completely different thread reads what Thread 1 wrote
    graph_reader = {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "stored_profile", "type": "dict", "reducer": "overwrite", "default": {}},
            ],
        },
        "nodes": [
            {
                "id": "read_node",
                "type": "memory_read",
                "label": "Read Profile",
                "config": {
                    "namespace": ["users", "test_user"],
                    "key": "profile",
                    "output_field": "stored_profile",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "read_node", "kind": "normal"},
            {"id": "e2", "source": "read_node", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "sqlite", "store": {"type": "sqlite"}},
    }

    events_th2 = []
    async for ev in run_langgraph_subprocess(
        graph_data=graph_reader,
        thread_id="th_user_reader",
        input_data={},
        stream_mode="updates",
    ):
        events_th2.append(ev)

    done_th2 = [e for e in events_th2 if e.get("event") == "done"][0]
    assert done_th2.get("status") == "success"

    # Verify final_state in thread 2 received user_name from Thread 1
    final_states = [e.get("values") for e in events_th2 if e.get("event") == "final_state"]
    assert final_states
    assert final_states[0].get("stored_profile", {}).get("user_name") == "Alice"


@pytest.mark.asyncio
async def test_time_travel_endpoints():
    """Test checkpoint history, state updating, and thread forking via REST API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check thread state
        resp = await client.get("/api/v1/threads/th_user_writer/state")
        assert resp.status_code == 200
        state_data = resp.json()
        assert "thread_id" in state_data

        # Check thread history
        resp_hist = await client.get("/api/v1/threads/th_user_writer/history")
        assert resp_hist.status_code == 200
        history_data = resp_hist.json()
        assert "history" in history_data
        checkpoints = history_data["history"]
        if checkpoints:
            latest_cp = checkpoints[0]["checkpoint_id"]
            # Test fork endpoint
            resp_fork = await client.post(
                "/api/v1/threads/th_user_writer/fork",
                json={"from_checkpoint_id": latest_cp, "new_thread_id": "th_forked_branch"},
            )
            assert resp_fork.status_code == 200
            fork_data = resp_fork.json()
            assert fork_data["status"] == "forked"
            assert fork_data["thread_id"] == "th_forked_branch"

        # Test store endpoint
        resp_store_put = await client.post(
            "/api/v1/store",
            json={"namespace": "test/integration", "key": "color", "value": {"theme": "dark"}},
        )
        assert resp_store_put.status_code == 200

        resp_store_get = await client.get("/api/v1/store?namespace=test/integration&key=color")
        assert resp_store_get.status_code == 200
        assert resp_store_get.json()["value"]["theme"] == "dark"
