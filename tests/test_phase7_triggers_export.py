"""
Tests for Phase 7: Triggers, Export, and Polish.
- Webhook trigger endpoint with optional secret token and payload mapping.
- Cron triggers via APScheduler (scheduling, updating, toggling active, deletion).
- Standalone project ZIP export containing state.py, nodes.py, graph.py, main.py,
  langgraph.json, requirements.txt, .env.example, README.md.
- Standalone project execution verification with USE_FAKE_LLM=1.
- Graph JSON import and export endpoints with validation.
- Security pass: secret redaction for API keys and tokens in logs/streams.
"""

import ast
import asyncio
from io import BytesIO
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from nocode_agent.main import app
from nocode_agent.database import get_db, ensure_tables
from nocode_agent.triggers import (
    get_scheduler,
    start_scheduler,
    stop_scheduler,
    resolve_thread_id,
    map_payload_to_input,
)
from nocode_agent.security import redact_secrets


@pytest.fixture(autouse=True)
async def setup_db_and_scheduler():
    await ensure_tables()
    start_scheduler()
    yield
    # Cleanup


@pytest.mark.asyncio
async def test_webhook_trigger_crud_and_execution():
    """Verify webhook trigger registration, authentication, payload mapping, and dispatch."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create a sample workflow
        wf_res = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Webhook Automation Flow",
                "graph": {
                    "schema_version": "1.0",
                    "state": {
                        "fields": [
                            {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                            {"name": "query", "type": "str", "reducer": "overwrite", "default": ""},
                        ],
                        "input_fields": ["messages", "query"],
                        "output_fields": ["messages"],
                    },
                    "nodes": [
                        {"id": "start", "type": "triggers", "label": "START", "position": {"x": 100, "y": 200}, "config": {}, "policy": {}},
                        {"id": "agent", "type": "agent", "label": "Agent", "position": {"x": 300, "y": 200}, "config": {"provider": "openai", "model": "gpt-4o-mini"}, "policy": {}},
                        {"id": "end", "type": "output", "label": "END", "position": {"x": 500, "y": 200}, "config": {}, "policy": {}},
                    ],
                    "edges": [
                        {"id": "e1", "source": "start", "target": "agent", "kind": "normal"},
                        {"id": "e2", "source": "agent", "target": "end", "kind": "normal"},
                    ],
                    "subgraphs": {},
                    "settings": {"checkpointer": "sqlite", "recursion_limit": 25, "interrupt_before": [], "interrupt_after": [], "store": {}, "config_fields": []},
                },
            },
        )
        assert wf_res.status_code in (200, 201), wf_res.text
        wf_id = wf_res.json()["id"]

        # 2. Register Webhook Trigger with secret token
        trig_res = await client.post(
            f"/api/v1/workflows/{wf_id}/triggers",
            json={
                "name": "GitHub Push Hook",
                "type": "webhook",
                "config": {
                    "path": "github/events",
                    "token": "gh_secret_token_12345",
                    "thread_id_rule": "static:gh_pipeline",
                    "payload_mapping": {
                        "query": "payload.commit_message",
                    },
                },
                "is_active": True,
            },
        )
        assert trig_res.status_code == 200, trig_res.text
        trig_data = trig_res.json()
        assert trig_data["id"].startswith("trig_")
        assert trig_data["is_active"] is True

        # 3. Test Webhook call without token -> should fail 401
        unauth_res = await client.post(
            f"/api/v1/webhook/{wf_id}/github/events",
            json={"commit_message": "Fix login bug"},
        )
        assert unauth_res.status_code == 401

        # 4. Test Webhook call with invalid token -> 401
        invalid_res = await client.post(
            f"/api/v1/webhook/{wf_id}/github/events",
            headers={"X-Webhook-Token": "wrong_secret"},
            json={"commit_message": "Fix login bug"},
        )
        assert invalid_res.status_code == 401

        # 5. Test Webhook call with valid token in query param
        valid_res = await client.post(
            f"/api/v1/webhook/{wf_id}/github/events?token=gh_secret_token_12345",
            json={"commit_message": "Deploy production build"},
        )
        assert valid_res.status_code == 200
        webhook_body = valid_res.json()
        assert webhook_body["status"] in ("triggered", "started")
        assert webhook_body["thread_id"] == "gh_pipeline"
        assert webhook_body["workflow_id"] == wf_id
        await asyncio.sleep(0.3)


@pytest.mark.asyncio
async def test_cron_trigger_scheduler_lifecycle():
    """Verify APScheduler integration for cron triggers: create, toggle, update, delete."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a workflow
        wf_res = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Scheduled Heartbeat Flow",
                "graph": {
                    "schema_version": "1.0",
                    "state": {"fields": [], "input_fields": [], "output_fields": []},
                    "nodes": [
                        {"id": "start", "type": "triggers", "label": "START", "position": {"x": 100, "y": 200}, "config": {}, "policy": {}},
                        {"id": "end", "type": "output", "label": "END", "position": {"x": 300, "y": 200}, "config": {}, "policy": {}},
                    ],
                    "edges": [{"id": "e1", "source": "start", "target": "end", "kind": "normal"}],
                    "subgraphs": {},
                    "settings": {"checkpointer": "sqlite", "recursion_limit": 25, "interrupt_before": [], "interrupt_after": [], "store": {}, "config_fields": []},
                },
            },
        )
        wf_id = wf_res.json()["id"]

        # 1. Create active cron trigger
        res = await client.post(
            f"/api/v1/workflows/{wf_id}/triggers",
            json={
                "name": "Daily Midnight Sync",
                "type": "cron",
                "config": {
                    "cron_expression": "0 0 * * *",
                    "thread_id_rule": "uuid",
                    "payload": {"task": "cleanup"},
                },
                "is_active": True,
            },
        )
        assert res.status_code == 200
        trig_data = res.json()
        trig_id = trig_data["id"]

        sched = get_scheduler()
        job = sched.get_job(trig_id)
        assert job is not None
        assert trig_data["is_active"] is True

        # 2. Toggle active -> False (should unschedule from APScheduler)
        up_res = await client.put(
            f"/api/v1/triggers/{trig_id}",
            json={"is_active": False},
        )
        assert up_res.status_code == 200
        assert up_res.json()["is_active"] is False
        assert sched.get_job(trig_id) is None

        # 3. Toggle active -> True (should reschedule in APScheduler)
        up_res2 = await client.put(
            f"/api/v1/triggers/{trig_id}",
            json={"is_active": True},
        )
        assert up_res2.status_code == 200
        assert up_res2.json()["is_active"] is True
        assert sched.get_job(trig_id) is not None

        # 4. Delete trigger -> unschedules and deletes from database
        del_res = await client.delete(f"/api/v1/triggers/{trig_id}")
        assert del_res.status_code == 200
        assert sched.get_job(trig_id) is None


@pytest.mark.asyncio
async def test_standalone_zip_export_and_standalone_execution():
    """Verify downloadable ZIP packages full project and runs standalone with USE_FAKE_LLM=1."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create workflow
        wf_res = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Exported Assistant",
                "graph": {
                    "schema_version": "1.0",
                    "state": {
                        "fields": [
                            {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                        ],
                        "input_fields": ["messages"],
                        "output_fields": ["messages"],
                    },
                    "nodes": [
                        {"id": "start", "type": "triggers", "label": "START", "position": {"x": 100, "y": 200}, "config": {}, "policy": {}},
                        {"id": "agent", "type": "agent", "label": "Reasoning Agent", "position": {"x": 300, "y": 200}, "config": {"provider": "openai", "model": "gpt-4o-mini"}, "policy": {}},
                        {"id": "end", "type": "output", "label": "END", "position": {"x": 500, "y": 200}, "config": {}, "policy": {}},
                    ],
                    "edges": [
                        {"id": "e1", "source": "start", "target": "agent", "kind": "normal"},
                        {"id": "e2", "source": "agent", "target": "end", "kind": "normal"},
                    ],
                    "subgraphs": {},
                    "settings": {"checkpointer": "sqlite", "recursion_limit": 25, "interrupt_before": [], "interrupt_after": [], "store": {}, "config_fields": []},
                },
            },
        )
        wf_id = wf_res.json()["id"]

        # 1. Download ZIP
        zip_res = await client.get(f"/api/v1/workflows/{wf_id}/export/zip")
        assert zip_res.status_code == 200
        assert zip_res.headers.get("content-type") == "application/zip"

        # 2. Inspect ZIP contents
        zip_bytes = zip_res.content
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            namelist = zf.namelist()
            # Must find root directory and standard LangGraph files
            basenames = [os.path.basename(n) for n in namelist if not n.endswith("/")]
            assert "state.py" in basenames
            assert "nodes.py" in basenames
            assert "graph.py" in basenames
            assert "main.py" in basenames
            assert "requirements.txt" in basenames
            assert "langgraph.json" in basenames
            assert ".env.example" in basenames
            assert "README.md" in basenames

            # Read README
            readme_entry = next(n for n in namelist if n.endswith("README.md"))
            readme_text = zf.read(readme_entry).decode("utf-8")
            assert "LangGraph Production Standalone Project" in readme_text
            assert "USE_FAKE_LLM=1" in readme_text

            # 3. Test standalone execution in isolated directory with USE_FAKE_LLM=1
            with tempfile.TemporaryDirectory() as temp_dir:
                zf.extractall(temp_dir)
                project_root = next(Path(temp_dir).iterdir())

                test_script = project_root / "test_standalone_runner.py"
                test_script.write_text(
                    "import asyncio\n"
                    "from graph import graph\n"
                    "async def main():\n"
                    "    res = await graph.ainvoke({'messages': [('user', 'Hello standalone test')]}, config={'configurable': {'thread_id': 't1'}})\n"
                    "    assert 'messages' in res\n"
                    "    print('STANDALONE_SUCCESS')\n"
                    "asyncio.run(main())\n",
                    encoding="utf-8",
                )

                env = os.environ.copy()
                env["USE_FAKE_LLM"] = "1"
                env["PYTHONPATH"] = str(project_root)
                env["CHECKPOINTS_DB_PATH"] = str(project_root / "standalone.db")

                proc = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=str(project_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert proc.returncode == 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
                assert "STANDALONE_SUCCESS" in proc.stdout


@pytest.mark.asyncio
async def test_graph_json_export_and_import():
    """Verify Graph JSON schema export and roundtrip import validation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create workflow
        wf_res = await client.post(
            "/api/v1/workflows",
            json={
                "name": "JSON Roundtrip Flow",
                "graph": {
                    "schema_version": "1.0",
                    "state": {"fields": [], "input_fields": [], "output_fields": []},
                    "nodes": [
                        {"id": "start", "type": "triggers", "label": "START", "position": {"x": 100, "y": 200}, "config": {}, "policy": {}},
                        {"id": "end", "type": "output", "label": "END", "position": {"x": 300, "y": 200}, "config": {}, "policy": {}},
                    ],
                    "edges": [{"id": "e1", "source": "start", "target": "end", "kind": "normal"}],
                    "subgraphs": {},
                    "settings": {"checkpointer": "sqlite", "recursion_limit": 25, "interrupt_before": [], "interrupt_after": [], "store": {}, "config_fields": []},
                },
            },
        )
        assert wf_res.status_code in (200, 201)
        wf_id = wf_res.json()["id"]

        # 1. Export JSON
        exp_res = await client.get(f"/api/v1/workflows/{wf_id}/export/json")
        assert exp_res.status_code == 200
        json_data = exp_res.json()
        assert json_data["id"] == wf_id
        assert json_data["name"] == "JSON Roundtrip Flow"
        assert len(json_data["graph"]["nodes"]) == 2

        # 2. Test Import with invalid graph (e.g. missing required start node) -> 400
        bad_import_res = await client.post(
            f"/api/v1/workflows/{wf_id}/import/json",
            json={
                "graph": {
                    "schema_version": "1.0",
                    "state": {"fields": []},
                    "nodes": [{"id": "orphan", "type": "agent", "label": "Agent", "position": {"x": 0, "y": 0}, "config": {}, "policy": {}}],
                    "edges": [],
                }
            },
        )
        assert bad_import_res.status_code == 400

        # 3. Test Import with valid expanded graph
        updated_graph = json_data["graph"]
        updated_graph["nodes"].append(
            {"id": "helper", "type": "agent", "label": "Helper Agent", "position": {"x": 200, "y": 200}, "config": {}, "policy": {}}
        )
        updated_graph["edges"].append(
            {"id": "e_start_helper", "source": "start", "target": "helper", "kind": "normal"}
        )
        updated_graph["edges"].append(
            {"id": "e_helper", "source": "helper", "target": "end", "kind": "normal"}
        )
        good_import_res = await client.post(
            f"/api/v1/workflows/{wf_id}/import/json",
            json={"name": "Renamed Import Flow", "graph": updated_graph},
        )
        assert good_import_res.status_code == 200
        body = good_import_res.json()
        assert body["status"] == "imported"
        assert body["name"] == "Renamed Import Flow"
        assert body["node_count"] == 3


def test_security_secret_redaction():
    """Verify regex secret sanitizer redacts sensitive API keys, tokens, and credentials."""
    raw_text = (
        "Connected to OpenAI sk-proj-1234567890abcdef1234567890 and "
        "Anthropic sk-ant-api03-abcdef1234567890abcdef1234567890 with "
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123 and "
        "Fernet gAAAAABnuV_0fK_testtoken1234567890=="
    )
    redacted = redact_secrets(raw_text)
    assert "sk-proj-1234567890" not in redacted
    assert "sk-ant-api03-" not in redacted
    assert "gAAAAABnuV" not in redacted
    assert "[REDACTED_SECRET]" in redacted

