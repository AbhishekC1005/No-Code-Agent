"""
No-Code Agent — FastAPI Backend (Self-Hosted / Local Edition)
SQLite persistence, optional JWT auth, static SPA serving, and visual agent execution.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
from typing import Any, Optional, Dict, List, Union
import zipfile
from pydantic import BaseModel, Field

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    AUTH_ENABLED,
    STATIC_DIR,
    DATA_DIR,
)
from .database import (
    ensure_tables,
    close_db,
    get_db,
    new_id,
    row_to_dict,
    get_sqlite_saver,
)
from .models import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceOut,
    ExecuteRequest,
    RunWorkflowRequest,
    UpdateStateRequest,
    ForkThreadRequest,
    VaultSave,
)
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)
import time
from .compiler import compile_graph
from .runner import execute_graph
from .engine.models import SingleNodeRunRequest, RerunFromRequest, ensure_item_list
from .engine.runner import execute_single_node
from .codegen import generate_langgraph_project
from .subprocess_runner import run_langgraph_subprocess, cancel_run
from .vault import encrypt_value, decrypt_value, mask_key
from .patterns import get_pattern_blocks, get_starter_templates
from .triggers import (
    start_scheduler,
    stop_scheduler,
    restore_active_triggers,
    schedule_cron_job,
    unschedule_cron_job,
    handle_webhook_trigger,
)


# ── Lifespan: initialize SQLite tables and clear stale runs on startup ────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_tables()
    # Mark any stale running runs as failed on startup
    try:
        db = await get_db()
        await db.execute(
            """
            UPDATE executions
            SET status = 'failed', error_message = 'Interrupted by server restart'
            WHERE status = 'running'
            """
        )
        await db.commit()
    except Exception:
        pass

    # Start trigger scheduler and restore active cron jobs
    try:
        await restore_active_triggers()
    except Exception:
        pass

    yield

    stop_scheduler()
    await close_db()


app = FastAPI(
    title="No-Code Agent Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS: restrict to localhost origins ───────────────────────────────────────

LOCAL_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    db = await get_db()
    cursor = await db.execute("SELECT id FROM users WHERE email = ?", (req.email,))
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = new_id()
    now_str = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO users (id, email, full_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, req.email, req.full_name, hash_password(req.password), now_str),
    )
    await db.commit()

    token = create_access_token({"sub": req.email, "uid": user_id})
    return AuthResponse(
        access_token=token,
        user={"id": user_id, "full_name": req.full_name, "email": req.email},
    )


@app.post("/api/v1/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE email = ?", (req.email,))
    row = await cursor.fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = row["id"]
    token = create_access_token({"sub": req.email, "uid": user_id})
    return AuthResponse(
        access_token=token,
        user={"id": user_id, "full_name": row["full_name"], "email": row["email"]},
    )


@app.get("/api/v1/auth/me")
async def get_me(user: dict = Depends(get_current_user_optional if not AUTH_ENABLED else get_current_user)):
    return {
        "id": user["id"],
        "full_name": user.get("full_name", "Local User"),
        "email": user.get("email", "admin@localhost"),
        "created_at": user.get("created_at"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# WORKSPACE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

def _format_workspace(d: dict) -> dict:
    created = d.get("created_at")
    updated = d.get("updated_at")
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created)
        except Exception:
            created = datetime.now(timezone.utc)
    if isinstance(updated, str):
        try:
            updated = datetime.fromisoformat(updated)
        except Exception:
            updated = datetime.now(timezone.utc)

    return {
        "id": str(d["id"]),
        "owner_id": str(d["owner_id"]),
        "name": d["name"],
        "nodes": d.get("nodes") if isinstance(d.get("nodes"), list) else [],
        "edges": d.get("edges") if isinstance(d.get("edges"), list) else [],
        "state_schema": d.get("state_schema") if isinstance(d.get("state_schema"), list) else [],
        "eval_rows": d.get("eval_rows") if isinstance(d.get("eval_rows"), list) else [],
        "created_at": created or datetime.now(timezone.utc),
        "updated_at": updated or datetime.now(timezone.utc),
    }


@app.get("/api/v1/workspaces")
async def list_workspaces(user: dict = Depends(get_current_user_optional)):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workspaces WHERE owner_id = ? ORDER BY updated_at DESC",
        (user["id"],),
    )
    rows = await cursor.fetchall()
    return [_format_workspace(row_to_dict(r)) for r in rows]


@app.post("/api/v1/workspaces", status_code=201)
async def create_workspace(
    req: WorkspaceCreate,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    ws_id = new_id()
    now_str = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO workspaces (id, owner_id, name, nodes, edges, state_schema, eval_rows, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ws_id,
            user["id"],
            req.name,
            json.dumps(req.nodes),
            json.dumps(req.edges),
            json.dumps(req.state_schema),
            json.dumps(req.eval_rows),
            now_str,
            now_str,
        ),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,))
    row = await cursor.fetchone()
    return _format_workspace(row_to_dict(row))


@app.get("/api/v1/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(get_current_user_optional)):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workspaces WHERE id = ? AND owner_id = ?",
        (workspace_id, user["id"]),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _format_workspace(row_to_dict(row))


@app.put("/api/v1/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    req: WorkspaceUpdate,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workspaces WHERE id = ? AND owner_id = ?",
        (workspace_id, user["id"]),
    )
    existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Workspace not found")

    updates = []
    params = []
    now_str = datetime.now(timezone.utc).isoformat()

    updates.append("updated_at = ?")
    params.append(now_str)

    if req.name is not None:
        updates.append("name = ?")
        params.append(req.name)
    if req.nodes is not None:
        updates.append("nodes = ?")
        params.append(json.dumps(req.nodes))
    if req.edges is not None:
        updates.append("edges = ?")
        params.append(json.dumps(req.edges))
    if req.state_schema is not None:
        updates.append("state_schema = ?")
        params.append(json.dumps(req.state_schema))
    if req.eval_rows is not None:
        updates.append("eval_rows = ?")
        params.append(json.dumps(req.eval_rows))

    params.extend([workspace_id, user["id"]])
    sql = f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ? AND owner_id = ?"
    await db.execute(sql, params)
    await db.commit()

    cursor = await db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
    updated_row = await cursor.fetchone()
    return _format_workspace(row_to_dict(updated_row))


@app.delete("/api/v1/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str, user: dict = Depends(get_current_user_optional)):
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM workspaces WHERE id = ? AND owner_id = ?",
        (workspace_id, user["id"]),
    )
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Workspace not found")


# ══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH NODE TYPES & WORKFLOWS CRUD
# ══════════════════════════════════════════════════════════════════════════════

NODE_TYPES = [
    {
        "type": "llm",
        "label": "LLM",
        "category": "models",
        "description": "Call language models (OpenAI, Anthropic, Ollama)",
        "color": "#9333EA",
        "default_config": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "systemPrompt": "You are a helpful AI assistant.",
            "ollamaBaseUrl": "http://localhost:11434",
        },
        "fields": [
            {"name": "provider", "label": "Provider", "type": "select", "options": ["openai", "anthropic", "ollama"], "default": "openai"},
            {"name": "model", "label": "Model Name", "type": "text", "default": "gpt-4o-mini"},
            {"name": "temperature", "label": "Temperature", "type": "number", "min": 0, "max": 2, "step": 0.1, "default": 0.7},
            {"name": "systemPrompt", "label": "System Prompt", "type": "textarea", "default": "You are a helpful AI assistant."},
            {"name": "ollamaBaseUrl", "label": "Ollama Base URL", "type": "text", "default": "http://localhost:11434"},
        ],
    },
    {
        "type": "tool",
        "label": "Tool",
        "category": "tools",
        "description": "LangChain tool or external HTTP API integration",
        "color": "#0D9488",
        "default_config": {
            "name": "web_search",
            "description": "Search the web for information",
            "url": "",
            "method": "GET",
            "use_tool_node": True,
        },
        "fields": [
            {"name": "name", "label": "Tool Name", "type": "text", "default": "web_search"},
            {"name": "description", "label": "Description", "type": "textarea", "default": "Search the web for information"},
            {"name": "url", "label": "Webhook / API URL", "type": "text", "placeholder": "https://api.example.com/endpoint"},
            {"name": "method", "label": "HTTP Method", "type": "select", "options": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            {"name": "use_tool_node", "label": "Wrap with LangGraph ToolNode", "type": "boolean", "default": True},
        ],
    },
    {
        "type": "function",
        "label": "Python Function",
        "category": "tools",
        "description": "Execute custom Python transformation on state",
        "color": "#10B981",
        "default_config": {
            "code": "return {'messages': state.get('messages', [])}",
        },
        "fields": [
            {"name": "code", "label": "Function Body (Python)", "type": "code", "default": "return {'messages': state.get('messages', [])}"},
        ],
    },
    {
        "type": "command",
        "label": "Command",
        "category": "logic",
        "description": "Dynamic routing with Command(goto=..., update=...)",
        "color": "#DB2777",
        "default_config": {
            "is_command": True,
            "condition": "len(state.get('messages', [])) > 0",
            "goto_true": "END",
            "goto_false": "agent",
            "update_true": {},
            "update_false": {},
        },
        "fields": [
            {"name": "condition", "label": "Condition Expression", "type": "text", "default": "len(state.get('messages', [])) > 0"},
            {"name": "goto_true", "label": "Target If True", "type": "text", "default": "END"},
            {"name": "goto_false", "label": "Target If False", "type": "text", "default": "agent"},
        ],
    },
    {
        "type": "map",
        "label": "Map (Send)",
        "category": "logic",
        "description": "Scatter-gather map-reduce using Send(target, {...})",
        "color": "#F59E0B",
        "default_config": {
            "is_map": True,
            "items_field": "items",
            "send_target": "worker",
        },
        "fields": [
            {"name": "items_field", "label": "State Items List Field", "type": "text", "default": "items"},
            {"name": "send_target", "label": "Target Worker Node", "type": "text", "default": "worker"},
        ],
    },
    {
        "type": "human",
        "label": "Human (HITL)",
        "category": "logic",
        "description": "Human-in-the-loop review with interrupt_before/after",
        "color": "#3B82F6",
        "default_config": {
            "review_prompt": "Please review and approve the draft.",
            "allow_edit": True,
        },
        "fields": [
            {"name": "review_prompt", "label": "Review Prompt", "type": "textarea", "default": "Please review and approve the draft."},
            {"name": "allow_edit", "label": "Allow State Editing", "type": "boolean", "default": True},
        ],
    },
    {
        "type": "subgraph",
        "label": "Subgraph",
        "category": "agents",
        "description": "Nested LangGraph flow with isolated or mapped state",
        "color": "#6366F1",
        "default_config": {
            "subgraph_name": "Nested Graph",
            "state_mapping": {},
        },
        "fields": [
            {"name": "subgraph_name", "label": "Subgraph Name", "type": "text", "default": "Nested Graph"},
        ],
    },
    {
        "type": "agent",
        "label": "Agent",
        "category": "agents",
        "description": "ReAct agent with tool execution loop",
        "color": "#E11D48",
        "default_config": {
            "provider": "openai",
            "model": "gpt-4o",
            "systemPrompt": "You are a reasoning agent capable of calling tools.",
        },
        "fields": [
            {"name": "provider", "label": "Provider", "type": "select", "options": ["openai", "anthropic", "ollama"], "default": "openai"},
            {"name": "model", "label": "Model Name", "type": "text", "default": "gpt-4o"},
            {"name": "systemPrompt", "label": "System Prompt", "type": "textarea", "default": "You are a reasoning agent capable of calling tools."},
        ],
    },
]

DEFAULT_GRAPH = {
    "schema_version": "1.0",
    "state": {
        "fields": [
            {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []}
        ],
        "input_fields": ["messages"],
        "output_fields": ["messages"],
    },
    "nodes": [
        {
            "id": "start",
            "type": "triggers",
            "label": "START",
            "position": {"x": 100, "y": 250},
            "config": {},
            "policy": {"retry": {}, "cache": {}, "defer": False},
        },
        {
            "id": "agent",
            "type": "agent",
            "label": "Reasoning Agent",
            "position": {"x": 380, "y": 250},
            "config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "systemPrompt": "You are a helpful AI assistant.",
            },
            "policy": {"retry": {}, "cache": {}, "defer": False},
        },
        {
            "id": "end",
            "type": "output",
            "label": "END",
            "position": {"x": 680, "y": 250},
            "config": {},
            "policy": {"retry": {}, "cache": {}, "defer": False},
        },
    ],
    "edges": [
        {"id": "e_start_agent", "source": "start", "target": "agent", "kind": "normal"},
        {"id": "e_agent_end", "source": "agent", "target": "end", "kind": "normal"},
    ],
    "subgraphs": {},
    "settings": {
        "checkpointer": "sqlite",
        "recursion_limit": 25,
        "interrupt_before": [],
        "interrupt_after": [],
        "store": {},
        "config_fields": [],
    },
}


@app.get("/api/v1/node-types")
@app.get("/node-types")
async def get_node_types():
    return NODE_TYPES


@app.get("/api/v1/workflows")
@app.get("/workflows")
async def list_workflows(user: dict = Depends(get_current_user_optional)):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workflows WHERE owner_id = ? ORDER BY updated_at DESC",
        (user["id"],),
    )
    rows = await cursor.fetchall()
    if not rows:
        wf_id = new_id()
        now_str = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            INSERT INTO workflows (id, owner_id, name, graph, schema_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, '1.0', ?, ?)
            """,
            (wf_id, user["id"], "My Agent Flow", json.dumps(DEFAULT_GRAPH), now_str, now_str),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,))
        rows = await cursor.fetchall()

    return [row_to_dict(r) for r in rows]


@app.post("/api/v1/workflows", status_code=201)
@app.post("/workflows", status_code=201)
async def create_workflow_endpoint(
    payload: dict[str, Any],
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    wf_id = new_id()
    name = payload.get("name") or "Untitled Flow"
    graph_data = payload.get("graph") or DEFAULT_GRAPH
    now_str = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO workflows (id, owner_id, name, graph, schema_version, created_at, updated_at)
        VALUES (?, ?, ?, ?, '1.0', ?, ?)
        """,
        (wf_id, user["id"], name, json.dumps(graph_data), now_str, now_str),
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,))
    row = await cursor.fetchone()
    return row_to_dict(row)


@app.get("/api/v1/workflows/{workflow_id}")
@app.get("/workflows/{workflow_id}")
async def get_workflow_endpoint(
    workflow_id: str,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workflows WHERE id = ? AND owner_id = ?",
        (workflow_id, user["id"]),
    )
    row = await cursor.fetchone()
    if not row:
        cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return row_to_dict(row)


@app.put("/api/v1/workflows/{workflow_id}")
@app.put("/workflows/{workflow_id}")
async def update_workflow_endpoint(
    workflow_id: str,
    payload: dict[str, Any],
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workflows WHERE id = ? AND owner_id = ?",
        (workflow_id, user["id"]),
    )
    existing = await cursor.fetchone()
    if not existing:
        cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Workflow not found")

    now_str = datetime.now(timezone.utc).isoformat()
    updates = ["updated_at = ?"]
    params = [now_str]

    if "name" in payload and payload["name"] is not None:
        updates.append("name = ?")
        params.append(payload["name"])
    if "graph" in payload and payload["graph"] is not None:
        updates.append("graph = ?")
        params.append(json.dumps(payload["graph"]) if isinstance(payload["graph"], dict) else str(payload["graph"]))

    params.append(workflow_id)
    await db.execute(f"UPDATE workflows SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    updated_row = await cursor.fetchone()
    return row_to_dict(updated_row)


@app.delete("/api/v1/workflows/{workflow_id}", status_code=204)
@app.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow_endpoint(
    workflow_id: str,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM workflows WHERE id = ? AND owner_id = ?",
        (workflow_id, user["id"]),
    )
    if cursor.rowcount == 0:
        await db.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    await db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH CODE GENERATION & EXPORT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/codegen")
async def codegen_endpoint(
    graph_data: dict[str, Any],
    user: dict = Depends(get_current_user_optional),
):
    """
    Accepts Graph JSON and generates real LangGraph Python files, sourcemap, and diagnostics.
    Runs in < 100 ms.
    """
    result = generate_langgraph_project(graph_data)
    return result


@app.get("/api/v1/workflows/{workflow_id}/export/project")
@app.get("/api/v1/workflows/{workflow_id}/export/zip")
@app.get("/api/v1/workspaces/{workflow_id}/export/project")
async def export_project_zip(
    workflow_id: str,
    user: dict = Depends(get_current_user_optional),
):
    """
    Export the full LangGraph project for a workflow as a downloadable ZIP.
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM workflows WHERE id = ? AND owner_id = ?",
        (workflow_id, user["id"]),
    )
    row = await cursor.fetchone()
    if not row:
        cursor = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    row_data = row_to_dict(row)
    graph_data = row_data.get("graph", {})
    if not graph_data or not isinstance(graph_data, dict):
        raise HTTPException(status_code=400, detail="Workflow has no valid graph data")

    codegen_res = generate_langgraph_project(graph_data)
    files = dict(codegen_res["files"])

    wf_name = re.sub(r"[^a-zA-Z0-9_-]", "_", row_data.get("name", "langgraph_project"))

    # Add .env.example
    files[".env.example"] = """# Standalone LangGraph Production Configuration
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
CHECKPOINTS_DB_PATH=checkpoints.db
STORE_DB_PATH=store.db
USE_FAKE_LLM=0
"""

    # Add README.md with standalone instructions
    files["README.md"] = f"""# {wf_name} – LangGraph Production Standalone Project

This project was automatically generated by No-Code Agent.
It is a fully standalone, native LangGraph workflow packaged with a FastAPI service.

## Prerequisites
- Python 3.10+
- Virtual environment (recommended)

## Setup
1. Create and activate a virtual environment:
```bash
python -m venv .venv
# On Windows:
.venv\\Scripts\\activate
# On Linux / macOS:
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Setup environment variables:
```bash
cp .env.example .env
```

## Running the Service
Start the FastAPI REST and streaming server:
```bash
python main.py
# or:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Running Standalone in CI with Fake Models
To test the workflow locally or in CI without making real external LLM API calls:
```bash
USE_FAKE_LLM=1 python -c "import asyncio; from graph import graph; res = asyncio.run(graph.ainvoke({{'messages': [('user', 'test message')]}})); print('Workflow Result:', res)"
```

## REST / Streaming API Usage
Invoke the workflow:
```bash
curl -X POST http://localhost:8000/run \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Hello!", "thread_id": "session_1"}}'
```

Stream tokens and state updates via SSE:
```bash
curl -N -X POST http://localhost:8000/run \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Hello!", "thread_id": "session_1", "stream": true}}'
```
"""

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            zf.writestr(f"{wf_name}/{fname}", content)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{wf_name}_project.zip"'},
    )


@app.get("/api/v1/workflows/{workflow_id}/export/json")
async def export_workflow_json(
    workflow_id: str,
    user: dict = Depends(get_current_user_optional),
):
    """Export workflow Graph JSON schema."""
    db = await get_db()
    cur = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    r_dict = row_to_dict(row)
    return {
        "id": r_dict["id"],
        "name": r_dict["name"],
        "schema_version": r_dict.get("schema_version", "1.0"),
        "graph": r_dict.get("graph", {}),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


class ImportGraphRequest(BaseModel):
    graph: Optional[dict[str, Any]] = None
    name: Optional[str] = None


@app.post("/api/v1/workflows/{workflow_id}/import/json")
async def import_workflow_json(
    workflow_id: str,
    req: ImportGraphRequest,
    user: dict = Depends(get_current_user_optional),
):
    """Import and validate Graph JSON schema for workflow."""
    graph_data = req.graph
    if not graph_data or not isinstance(graph_data, dict):
        raise HTTPException(status_code=400, detail="Invalid Graph JSON provided.")

    from .codegen.validator import validate_graph
    diagnostics = validate_graph(graph_data)
    errors = [d for d in diagnostics if d.get("level") == "error"]
    if errors:
        raise HTTPException(status_code=400, detail=f"Graph validation failed: {errors[0].get('message')}")

    db = await get_db()
    cur = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")

    now_str = datetime.now(timezone.utc).isoformat()
    new_name = req.name or row["name"]
    await db.execute(
        """
        UPDATE workflows
        SET graph = ?, name = ?, updated_at = ?
        WHERE id = ?
        """,
        (json.dumps(graph_data), new_name, now_str, workflow_id),
    )
    await db.commit()

    return {
        "status": "imported",
        "workflow_id": workflow_id,
        "name": new_name,
        "node_count": len(graph_data.get("nodes", [])),
        "edge_count": len(graph_data.get("edges", [])),
        "updated_at": now_str,
    }


@app.get("/api/v1/workflows/{workflow_id}/executions")
async def list_workflow_executions(
    workflow_id: str,
    user: dict = Depends(get_current_user_optional),
):
    """List execution history runs for workflow."""
    db = await get_db()
    cur = await db.execute(
        """
        SELECT id, workflow_id, thread_id, mode, status, start_time, end_time, total_ms, error_message, created_at
        FROM executions
        WHERE workflow_id = ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (workflow_id,),
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# TRIGGERS (WEBHOOKS & CRON)
# ══════════════════════════════════════════════════════════════════════════════

class TriggerCreate(BaseModel):
    name: str
    type: str  # 'webhook' or 'cron'
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class TriggerUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


@app.get("/api/v1/workflows/{workflow_id}/triggers")
async def list_workflow_triggers(
    workflow_id: str,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM triggers WHERE workflow_id = ? ORDER BY created_at DESC",
        (workflow_id,),
    )
    rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["config"] = json.loads(d["config"]) if isinstance(d["config"], str) else d["config"]
        d["is_active"] = bool(d["is_active"])
        result.append(d)
    return result


@app.post("/api/v1/workflows/{workflow_id}/triggers")
async def create_workflow_trigger(
    workflow_id: str,
    req: TriggerCreate,
    user: dict = Depends(get_current_user_optional),
):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Trigger name cannot be empty")
    ttype = req.type.lower()
    if ttype not in ("webhook", "cron"):
        raise HTTPException(status_code=400, detail="Trigger type must be 'webhook' or 'cron'")

    db = await get_db()
    tid = f"trig_{new_id()[:12]}"
    now_str = datetime.now(timezone.utc).isoformat()
    cfg_json = json.dumps(req.config or {})

    await db.execute(
        """
        INSERT INTO triggers (id, workflow_id, name, type, config, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tid, workflow_id, req.name.strip(), ttype, cfg_json, 1 if req.is_active else 0, now_str, now_str),
    )
    await db.commit()

    trigger_data = {
        "id": tid,
        "workflow_id": workflow_id,
        "name": req.name.strip(),
        "type": ttype,
        "config": req.config,
        "is_active": req.is_active,
        "last_run": None,
        "created_at": now_str,
        "updated_at": now_str,
    }

    if ttype == "cron" and req.is_active:
        schedule_cron_job(trigger_data)

    return trigger_data


@app.put("/api/v1/triggers/{trigger_id}")
async def update_trigger(
    trigger_id: str,
    req: TriggerUpdate,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cur = await db.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Trigger not found")

    r_dict = dict(row)
    new_name = req.name if req.name is not None else r_dict["name"]
    new_cfg = json.dumps(req.config) if req.config is not None else r_dict["config"]
    new_active = (1 if req.is_active else 0) if req.is_active is not None else r_dict["is_active"]
    now_str = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """
        UPDATE triggers
        SET name = ?, config = ?, is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_name, new_cfg, new_active, now_str, trigger_id),
    )
    await db.commit()

    updated = {
        "id": trigger_id,
        "workflow_id": r_dict["workflow_id"],
        "name": new_name,
        "type": r_dict["type"],
        "config": json.loads(new_cfg) if isinstance(new_cfg, str) else new_cfg,
        "is_active": bool(new_active),
        "last_run": r_dict["last_run"],
        "updated_at": now_str,
    }

    if r_dict["type"] == "cron":
        if new_active:
            schedule_cron_job(updated)
        else:
            unschedule_cron_job(trigger_id)

    return updated


@app.delete("/api/v1/triggers/{trigger_id}")
async def delete_trigger(
    trigger_id: str,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cur = await db.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Trigger not found")

    r_dict = dict(row)
    if r_dict["type"] == "cron":
        unschedule_cron_job(trigger_id)

    await db.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
    await db.commit()
    return {"status": "deleted", "id": trigger_id}


# Webhook receiver endpoint
@app.api_route("/api/v1/webhook/{workflow_id}/{path:path}", methods=["GET", "POST", "PUT"])
async def webhook_endpoint(
    workflow_id: str,
    path: str,
    request: Request,
):
    token = request.headers.get("X-Webhook-Token") or request.query_params.get("token")
    payload = {}
    if request.method in ("POST", "PUT"):
        try:
            payload = await request.json()
        except Exception:
            body_bytes = await request.body()
            if body_bytes:
                payload = {"raw": body_bytes.decode(errors="ignore")}
    else:
        payload = dict(request.query_params)

    return await handle_webhook_trigger(workflow_id, path, payload, token)


@app.post("/api/v1/workspaces/{workspace_id}/compile")
async def compile_workspace(workspace_id: str, user: dict = Depends(get_current_user_optional)):
    """Legacy backward-compatibility compile endpoint returning ZIP."""
    return await export_project_zip(workspace_id, user)


# ══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH RUNNER & THREAD STATE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/runs")
@app.post("/runs")
async def create_run_endpoint(
    req: RunWorkflowRequest,
    user: dict = Depends(get_current_user_optional),
):
    """
    Execute generated LangGraph code in a worker subprocess, streaming events as SSE.
    """
    db = await get_db()

    # Load graph from workflow if not explicitly in request body
    graph_data = req.graph
    if not graph_data:
        cursor = await db.execute("SELECT graph FROM workflows WHERE id = ?", (req.workflow_id,))
        row = await cursor.fetchone()
        if row:
            row_dict = row_to_dict(row)
            graph_data = row_dict.get("graph")

    if not graph_data or not isinstance(graph_data, dict):
        raise HTTPException(status_code=400, detail="No valid graph data found to execute")

    # Fetch stored credentials from vault
    cursor = await db.execute("SELECT * FROM credentials WHERE owner_id = ?", (user["id"],))
    cred_row = await cursor.fetchone()

    credentials: dict[str, str] = {
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "pinecone_key": os.getenv("PINECONE_API_KEY", ""),
    }
    if cred_row:
        for k in ("openai_key", "anthropic_key", "pinecone_key"):
            if cred_row[k]:
                dec = decrypt_value(cred_row[k])
                if dec:
                    credentials[k] = dec

    run_id = f"run_{new_id()}"

    async def sse_event_stream():
        async for event in run_langgraph_subprocess(
            graph_data=graph_data,
            workflow_id=req.workflow_id,
            thread_id=req.thread_id,
            run_id=run_id,
            input_data=req.input,
            message=req.message,
            resume=req.resume,
            checkpoint_id=req.checkpoint_id,
            stream_mode=req.stream_mode,
            credentials=credentials,
            timeout_seconds=req.timeout_seconds,
            owner_id=user["id"],
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Run-ID": run_id,
        },
    )


@app.post("/api/v1/runs/{run_id}/cancel")
@app.post("/runs/{run_id}/cancel")
async def cancel_run_endpoint(
    run_id: str,
    user: dict = Depends(get_current_user_optional),
):
    """Cancel an active running worker subprocess."""
    success = await cancel_run(run_id)
    if not success:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM executions WHERE id = ?", (run_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Run not found")
        return {"status": "not_running", "message": "Run is not currently active"}
    return {"status": "cancelled", "run_id": run_id}


@app.get("/api/v1/threads")
@app.get("/threads")
async def list_threads_endpoint(user: dict = Depends(get_current_user_optional)):
    """List distinct threads with their latest run status and checkpoint info."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT thread_id, MAX(start_time) as last_active, COUNT(id) as run_count,
               MAX(status) as last_status
        FROM executions
        WHERE owner_id = ?
        GROUP BY thread_id
        ORDER BY last_active DESC
        """,
        (user["id"],),
    )
    rows = await cursor.fetchall()
    threads = [
        {
            "thread_id": r["thread_id"],
            "last_active": r["last_active"],
            "run_count": r["run_count"],
            "last_status": r["last_status"],
        }
        for r in rows
    ]
    if not threads:
        threads = [{"thread_id": "default", "last_active": datetime.now(timezone.utc).isoformat(), "run_count": 0, "last_status": "idle"}]
    return threads


@app.get("/api/v1/threads/{thread_id}/state")
@app.get("/threads/{thread_id}/state")
async def get_thread_state_endpoint(
    thread_id: str,
    checkpoint_id: Optional[str] = None,
    user: dict = Depends(get_current_user_optional),
):
    """Retrieve checkpoint state for a thread from checkpoints.db."""
    try:
        saver = get_sqlite_saver()
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        cp_tuple = saver.get_tuple(config)
        if not cp_tuple or not cp_tuple.checkpoint:
            return {"thread_id": thread_id, "checkpoint_id": None, "values": {}, "next": []}
        return {
            "thread_id": thread_id,
            "checkpoint_id": cp_tuple.checkpoint.get("id"),
            "values": cp_tuple.checkpoint.get("channel_values", {}),
            "next": list(getattr(cp_tuple, "next", [])) if getattr(cp_tuple, "next", None) else [],
            "metadata": cp_tuple.metadata,
        }
    except Exception as exc:
        return {"thread_id": thread_id, "checkpoint_id": None, "values": {}, "error": str(exc)}


@app.post("/api/v1/threads/{thread_id}/state")
@app.post("/threads/{thread_id}/state")
async def update_thread_state_endpoint(
    thread_id: str,
    req: UpdateStateRequest,
    user: dict = Depends(get_current_user_optional),
):
    """Time Travel: update state values for a thread checkpoint (update_state with as_node)."""
    try:
        saver = get_sqlite_saver()
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        if req.checkpoint_id:
            config["configurable"]["checkpoint_id"] = req.checkpoint_id

        cp_tuple = saver.get_tuple(config)
        current_values = dict(cp_tuple.checkpoint.get("channel_values", {})) if cp_tuple and cp_tuple.checkpoint else {}
        current_values.update(req.values)

        new_cp_id = new_id()
        checkpoint = {
            "v": 1,
            "id": new_cp_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "channel_values": current_values,
            "channel_versions": {k: 1 for k in current_values},
            "versions_seen": {},
        }
        metadata = {
            "source": "update_state",
            "step": (cp_tuple.metadata.get("step", 0) if cp_tuple and cp_tuple.metadata else 0) + 1,
            "as_node": req.as_node or "user_edit",
        }
        saver.put(config, checkpoint, metadata, {})
        return {"status": "updated", "checkpoint_id": new_cp_id, "values": current_values}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update thread state: {exc}")


@app.post("/api/v1/threads/{thread_id}/fork")
@app.post("/threads/{thread_id}/fork")
async def fork_thread_endpoint(
    thread_id: str,
    req: ForkThreadRequest,
    user: dict = Depends(get_current_user_optional),
):
    """Time Travel: fork an existing thread starting from a specific checkpoint."""
    new_tid = req.new_thread_id or f"fork_{new_id()[:8]}"
    try:
        saver = get_sqlite_saver()
        src_config = {"configurable": {"thread_id": thread_id, "checkpoint_id": req.from_checkpoint_id, "checkpoint_ns": ""}}
        cp_tuple = saver.get_tuple(src_config)
        if not cp_tuple or not cp_tuple.checkpoint:
            raise HTTPException(status_code=404, detail=f"Checkpoint {req.from_checkpoint_id} not found in thread {thread_id}")

        dest_config = {"configurable": {"thread_id": new_tid, "checkpoint_ns": ""}}
        new_cp_id = new_id()
        checkpoint = dict(cp_tuple.checkpoint)
        checkpoint["id"] = new_cp_id
        checkpoint["ts"] = datetime.now(timezone.utc).isoformat()
        metadata = {
            "source": "fork",
            "from_thread_id": thread_id,
            "from_checkpoint_id": req.from_checkpoint_id,
        }
        saver.put(dest_config, checkpoint, metadata, {})

        db = await get_db()
        await db.execute(
            """
            INSERT INTO executions (id, workflow_id, owner_id, thread_id, mode, status, start_time)
            VALUES (?, 'fork', ?, ?, 'fork', 'idle', ?)
            """,
            (f"exec_{new_id()[:8]}", user["id"], new_tid, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

        return {
            "status": "forked",
            "thread_id": new_tid,
            "checkpoint_id": new_cp_id,
            "values": checkpoint.get("channel_values", {}),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fork thread: {exc}")


@app.get("/api/v1/threads/{thread_id}/history")
@app.get("/threads/{thread_id}/history")
async def get_thread_history_endpoint(
    thread_id: str,
    user: dict = Depends(get_current_user_optional),
):
    """Retrieve full history checkpoints and parent links for a thread from checkpoints.db."""
    try:
        saver = get_sqlite_saver()
        config = {"configurable": {"thread_id": thread_id}}
        history = []
        for cp in saver.list(config):
            parent_cid = cp.parent_config.get("configurable", {}).get("checkpoint_id") if cp.parent_config else None
            history.append({
                "checkpoint_id": cp.checkpoint.get("id"),
                "parent_checkpoint_id": parent_cid,
                "values": cp.checkpoint.get("channel_values", {}),
                "next": list(getattr(cp, "next", [])) if getattr(cp, "next", None) else [],
                "metadata": cp.metadata,
            })
        return {"thread_id": thread_id, "history": history}
    except Exception as exc:
        return {"thread_id": thread_id, "history": [], "error": str(exc)}


@app.get("/api/v1/store")
@app.get("/store")
async def list_store_items(
    namespace: str = "memories",
    key: Optional[str] = None,
    user: dict = Depends(get_current_user_optional),
):
    """Inspect memory store items by namespace."""
    from langgraph.store.sqlite import SqliteStore
    store_path = str(DATA_DIR / "store.db")
    with SqliteStore.from_conn_string(store_path) as store:
        store.setup()
        ns_tuple = tuple(namespace.split("/"))
        if key:
            item = store.get(ns_tuple, key)
            return {"namespace": namespace, "key": key, "value": item.value if item else None}
        items = store.search(ns_tuple)
        return {
            "namespace": namespace,
            "items": [{"key": i.key, "value": i.value, "updated_at": getattr(i, "updated_at", None)} for i in items],
        }


@app.post("/api/v1/store")
@app.post("/store")
async def put_store_item(
    payload: dict[str, Any],
    user: dict = Depends(get_current_user_optional),
):
    """Write an item into persistent memory store namespace."""
    from langgraph.store.sqlite import SqliteStore
    store_path = str(DATA_DIR / "store.db")
    with SqliteStore.from_conn_string(store_path) as store:
        store.setup()
        namespace = payload.get("namespace", "memories")
        key = payload.get("key", "default")
        val = payload.get("value", {})
        ns_tuple = tuple(namespace.split("/"))
        store.put(ns_tuple, key, val)
        return {"status": "stored", "namespace": namespace, "key": key}


# ══════════════════════════════════════════════════════════════════════════════
# N8N-STYLE BACKEND EXECUTION & SSE STREAMING
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/execute")
async def execute_agent_workflow(
    req: ExecuteRequest,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM credentials WHERE owner_id = ?",
        (user["id"],),
    )
    cred_row = await cursor.fetchone()

    credentials: dict[str, str] = {
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "pinecone_key": os.getenv("PINECONE_API_KEY", ""),
    }

    if cred_row:
        if cred_row["openai_key"]:
            dec = decrypt_value(cred_row["openai_key"])
            if dec:
                credentials["openai_key"] = dec
        if cred_row["anthropic_key"]:
            dec = decrypt_value(cred_row["anthropic_key"])
            if dec:
                credentials["anthropic_key"] = dec
        if cred_row["pinecone_key"]:
            dec = decrypt_value(cred_row["pinecone_key"])
            if dec:
                credentials["pinecone_key"] = dec

    async def sse_event_generator():
        final_answer = ""
        visited_nodes = []
        total_ms = 0
        node_traces = []

        async for event in execute_graph(
            nodes=req.nodes,
            edges=req.edges,
            user_input=req.message,
            credentials=credentials,
            thread_id=req.thread_id,
        ):
            if event.get("event") == "node_end":
                node_traces.append(event)
            elif event.get("event") == "done":
                final_answer = event.get("finalAnswer", "")
                visited_nodes = event.get("visitedNodes", [])
                total_ms = event.get("totalMs", 0)

            yield f"data: {json.dumps(event)}\n\n"

        # Log execution to SQLite
        try:
            log_db = await get_db()
            await log_db.execute(
                """
                INSERT INTO execution_logs (id, owner_id, thread_id, input_message, final_answer, visited_nodes, total_ms, node_traces, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(),
                    user["id"],
                    req.thread_id,
                    req.message,
                    final_answer,
                    json.dumps(visited_nodes),
                    total_ms,
                    json.dumps(node_traces),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await log_db.commit()
        except Exception:
            pass

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/v1/nodes/run-single")
async def run_single_node_endpoint(
    req: SingleNodeRunRequest,
    user: dict = Depends(get_current_user_optional),
):
    """
    Run a single node with provided/pinned input data.
    """
    db = await get_db()
    cursor = await db.execute("SELECT * FROM credentials WHERE owner_id = ?", (user["id"],))
    cred_row = await cursor.fetchone()

    credentials: dict[str, str] = {
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "pinecone_key": os.getenv("PINECONE_API_KEY", ""),
    }
    credentials.update(req.credentials)

    if cred_row:
        if cred_row["openai_key"]:
            dec = decrypt_value(cred_row["openai_key"])
            if dec:
                credentials["openai_key"] = dec
        if cred_row["anthropic_key"]:
            dec = decrypt_value(cred_row["anthropic_key"])
            if dec:
                credentials["anthropic_key"] = dec
        if cred_row["pinecone_key"]:
            dec = decrypt_value(cred_row["pinecone_key"])
            if dec:
                credentials["pinecone_key"] = dec

    t_start = time.perf_counter()
    tokens: list[str] = []

    async def token_emitter(delta: str):
        tokens.append(delta)

    try:
        ports_result = await execute_single_node(
            node=req.node,
            input_items=req.input_items,
            connected_tools=req.connected_tools,
            credentials=credentials,
            node_context=req.node_outputs,
            on_token=token_emitter,
        )
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        return {
            "status": "success",
            "ports": {str(k): v for k, v in ports_result.items()},
            "latencyMs": latency_ms,
            "tokens": tokens,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": str(exc),
                "latencyMs": latency_ms,
            },
        )


@app.post("/api/v1/nodes/rerun-from")
async def rerun_from_node_endpoint(
    req: RerunFromRequest,
    user: dict = Depends(get_current_user_optional),
):
    """
    Re-runs a workflow starting from a specific node with pinned input items.
    """
    db = await get_db()
    cursor = await db.execute("SELECT * FROM credentials WHERE owner_id = ?", (user["id"],))
    cred_row = await cursor.fetchone()

    credentials: dict[str, str] = {
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "pinecone_key": os.getenv("PINECONE_API_KEY", ""),
    }
    credentials.update(req.credentials)

    if cred_row:
        if cred_row["openai_key"]:
            dec = decrypt_value(cred_row["openai_key"])
            if dec:
                credentials["openai_key"] = dec
        if cred_row["anthropic_key"]:
            dec = decrypt_value(cred_row["anthropic_key"])
            if dec:
                credentials["anthropic_key"] = dec
        if cred_row["pinecone_key"]:
            dec = decrypt_value(cred_row["pinecone_key"])
            if dec:
                credentials["pinecone_key"] = dec

    async def sse_event_generator():
        async for event in execute_graph(
            nodes=req.nodes,
            edges=req.edges,
            user_input="",
            credentials=credentials,
            thread_id=req.thread_id,
            start_node_id=req.start_node_id,
            initial_items=req.pinned_input_items,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# SERVER-SIDE CREDENTIAL VAULT
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/vault")
async def get_vault_credentials(user: dict = Depends(get_current_user_optional)):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM credentials WHERE owner_id = ?", (user["id"],))
    cred_row = await cursor.fetchone()

    openai_raw = os.getenv("OPENAI_API_KEY", "")
    anthropic_raw = os.getenv("ANTHROPIC_API_KEY", "")
    pinecone_raw = os.getenv("PINECONE_API_KEY", "")

    if cred_row:
        if cred_row["openai_key"]:
            dec = decrypt_value(cred_row["openai_key"])
            if dec:
                openai_raw = dec
        if cred_row["anthropic_key"]:
            dec = decrypt_value(cred_row["anthropic_key"])
            if dec:
                anthropic_raw = dec
        if cred_row["pinecone_key"]:
            dec = decrypt_value(cred_row["pinecone_key"])
            if dec:
                pinecone_raw = dec

    return {
        "openai_masked": mask_key(openai_raw),
        "anthropic_masked": mask_key(anthropic_raw),
        "pinecone_masked": mask_key(pinecone_raw),
        "has_openai": bool(openai_raw),
        "has_anthropic": bool(anthropic_raw),
        "has_pinecone": bool(pinecone_raw),
    }


@app.post("/api/v1/vault")
async def save_vault_credentials(
    req: VaultSave,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM credentials WHERE owner_id = ?", (user["id"],))
    existing = await cursor.fetchone()

    openai_enc = encrypt_value(req.openai_key) if req.openai_key else (existing["openai_key"] if existing else "")
    anthropic_enc = encrypt_value(req.anthropic_key) if req.anthropic_key else (existing["anthropic_key"] if existing else "")
    pinecone_enc = encrypt_value(req.pinecone_key) if req.pinecone_key else (existing["pinecone_key"] if existing else "")
    now_str = datetime.now(timezone.utc).isoformat()

    if existing:
        await db.execute(
            """
            UPDATE credentials
            SET openai_key = ?, anthropic_key = ?, pinecone_key = ?, updated_at = ?
            WHERE owner_id = ?
            """,
            (openai_enc, anthropic_enc, pinecone_enc, now_str, user["id"]),
        )
    else:
        await db.execute(
            """
            INSERT INTO credentials (id, owner_id, openai_key, anthropic_key, pinecone_key, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (new_id(), user["id"], openai_enc, anthropic_enc, pinecone_enc, now_str),
        )

    await db.commit()
    return {"status": "saved", "message": "Credentials encrypted and saved to local SQLite database."}


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC TYPED CREDENTIALS (PHASE 6)
# ══════════════════════════════════════════════════════════════════════════════

class TypedCredentialCreate(BaseModel):
    name: str
    type: str  # openai, anthropic, ollama, bearer, custom
    value: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TypedCredentialUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CredentialTestRequest(BaseModel):
    type: str
    value: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _test_credential_connectivity(cred_type: str, raw_key: str, metadata: dict[str, Any]) -> dict[str, Any]:
    import httpx
    ctype = cred_type.lower()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if ctype == "openai":
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
                if resp.status_code == 200:
                    return {"success": True, "status_code": 200, "message": "Successfully connected to OpenAI API."}
                elif resp.status_code == 401:
                    return {"success": False, "status_code": 401, "message": "Authentication failed: Invalid OpenAI API key."}
                else:
                    return {"success": False, "status_code": resp.status_code, "message": f"OpenAI returned status {resp.status_code}"}

            elif ctype == "anthropic":
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": raw_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                if resp.status_code == 200:
                    return {"success": True, "status_code": 200, "message": "Successfully connected to Anthropic API."}
                elif resp.status_code == 401:
                    return {"success": False, "status_code": 401, "message": "Authentication failed: Invalid Anthropic API key."}
                else:
                    return {"success": False, "status_code": resp.status_code, "message": f"Anthropic returned status {resp.status_code}"}

            elif ctype == "ollama":
                base_url = metadata.get("base_url") or raw_key or "http://localhost:11434"
                base_url = base_url.rstrip("/")
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return {"success": True, "status_code": 200, "message": f"Connected to Ollama. Models: {', '.join(models[:4]) if models else 'None'}"}
                else:
                    return {"success": False, "status_code": resp.status_code, "message": f"Ollama returned status {resp.status_code}"}

            elif ctype in ("bearer", "custom"):
                test_url = metadata.get("test_url")
                if not test_url:
                    if raw_key and len(raw_key) > 3:
                        return {"success": True, "status_code": 200, "message": "Credential format is valid (no test URL provided)."}
                    return {"success": False, "status_code": 400, "message": "Empty or invalid credential value."}
                header_name = metadata.get("header_name", "Authorization")
                header_val = f"Bearer {raw_key}" if ctype == "bearer" and not raw_key.startswith("Bearer ") else raw_key
                resp = await client.get(test_url, headers={header_name: header_val})
                if resp.status_code in (200, 201, 204):
                    return {"success": True, "status_code": resp.status_code, "message": f"Connected successfully (status {resp.status_code})."}
                else:
                    return {"success": False, "status_code": resp.status_code, "message": f"Endpoint returned status {resp.status_code}"}

            else:
                return {"success": True, "status_code": 200, "message": f"Credential type '{ctype}' accepted."}
    except Exception as exc:
        return {"success": False, "status_code": 500, "message": f"Connection error: {str(exc)}"}


@app.get("/api/v1/credentials")
async def list_typed_credentials(user: dict = Depends(get_current_user_optional)):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, owner_id, name, type, encrypted_value, metadata, created_at, updated_at FROM typed_credentials WHERE owner_id = ? ORDER BY created_at DESC",
        (user["id"],),
    )
    rows = await cur.fetchall()
    result = []
    for r in rows:
        r_dict = dict(r)
        raw_val = decrypt_value(r_dict.pop("encrypted_value", ""))
        r_dict["masked_value"] = mask_key(raw_val)
        try:
            r_dict["metadata"] = json.loads(r_dict.get("metadata") or "{}")
        except Exception:
            r_dict["metadata"] = {}
        result.append(r_dict)
    return result


@app.post("/api/v1/credentials")
async def create_typed_credential(
    req: TypedCredentialCreate,
    user: dict = Depends(get_current_user_optional),
):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Credential name cannot be empty")
    if not req.value.strip():
        raise HTTPException(status_code=400, detail="Credential value cannot be empty")

    db = await get_db()
    cid = f"cred_{new_id()[:12]}"
    enc_val = encrypt_value(req.value.strip())
    meta_str = json.dumps(req.metadata or {})
    now_str = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """
        INSERT INTO typed_credentials (id, owner_id, name, type, encrypted_value, metadata, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cid, user["id"], req.name.strip(), req.type.lower(), enc_val, meta_str, now_str, now_str),
    )
    await db.commit()

    return {
        "id": cid,
        "name": req.name.strip(),
        "type": req.type.lower(),
        "masked_value": mask_key(req.value.strip()),
        "metadata": req.metadata,
        "created_at": now_str,
        "updated_at": now_str,
    }


@app.put("/api/v1/credentials/{cred_id}")
async def update_typed_credential(
    cred_id: str,
    req: TypedCredentialUpdate,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cur = await db.execute("SELECT * FROM typed_credentials WHERE id = ? AND owner_id = ?", (cred_id, user["id"]))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Credential not found")

    r_dict = dict(row)
    new_name = req.name if req.name is not None else r_dict["name"]
    new_enc = encrypt_value(req.value.strip()) if req.value else r_dict["encrypted_value"]
    new_meta = json.dumps(req.metadata) if req.metadata is not None else r_dict["metadata"]
    now_str = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """
        UPDATE typed_credentials
        SET name = ?, encrypted_value = ?, metadata = ?, updated_at = ?
        WHERE id = ? AND owner_id = ?
        """,
        (new_name, new_enc, new_meta, now_str, cred_id, user["id"]),
    )
    await db.commit()

    return {
        "id": cred_id,
        "name": new_name,
        "type": r_dict["type"],
        "masked_value": mask_key(decrypt_value(new_enc)),
        "metadata": json.loads(new_meta) if isinstance(new_meta, str) else new_meta,
        "updated_at": now_str,
    }


@app.delete("/api/v1/credentials/{cred_id}")
async def delete_typed_credential(
    cred_id: str,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cur = await db.execute("DELETE FROM typed_credentials WHERE id = ? AND owner_id = ?", (cred_id, user["id"]))
    await db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "deleted", "id": cred_id}


@app.post("/api/v1/credentials/{cred_id}/test")
async def test_saved_credential(
    cred_id: str,
    user: dict = Depends(get_current_user_optional),
):
    db = await get_db()
    cur = await db.execute("SELECT * FROM typed_credentials WHERE id = ? AND owner_id = ?", (cred_id, user["id"]))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Credential not found")
    raw_val = decrypt_value(row["encrypted_value"])
    try:
        meta = json.loads(row["metadata"] or "{}")
    except Exception:
        meta = {}
    return await _test_credential_connectivity(row["type"], raw_val, meta)


@app.post("/api/v1/credentials/test")
async def test_raw_credential(req: CredentialTestRequest):
    return await _test_credential_connectivity(req.type, req.value or "", req.metadata)


# ══════════════════════════════════════════════════════════════════════════════
# PATTERNS & STARTER TEMPLATES (PHASE 6)
# ══════════════════════════════════════════════════════════════════════════════

class PatternInstantiateRequest(BaseModel):
    offset_x: float = 300.0
    offset_y: float = 200.0


@app.get("/api/v1/patterns")
async def list_patterns():
    patterns = get_pattern_blocks()
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "description": p["description"],
            "icon": p["icon"],
        }
        for p in patterns
    ]


@app.post("/api/v1/patterns/{pattern_id}/instantiate")
async def instantiate_pattern(pattern_id: str, req: PatternInstantiateRequest = PatternInstantiateRequest()):
    patterns = {p["id"]: p for p in get_pattern_blocks()}
    if pattern_id not in patterns:
        raise HTTPException(status_code=404, detail=f"Pattern '{pattern_id}' not found")
    builder = patterns[pattern_id]["builder"]
    result = builder(offset_x=req.offset_x, offset_y=req.offset_y)
    return result


@app.get("/api/v1/templates")
async def list_starter_templates():
    templates = get_starter_templates()
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "description": t["description"],
            "complexity": t["complexity"],
            "node_count": len(t["graph"]["nodes"]),
            "edge_count": len(t["graph"]["edges"]),
        }
        for t in templates
    ]


@app.get("/api/v1/templates/{template_id}")
async def get_starter_template(template_id: str):
    templates = {t["id"]: t for t in get_starter_templates()}
    if template_id not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return templates[template_id]


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "service": "nocode-agent",
        "auth_enabled": AUTH_ENABLED,
        "database": "sqlite",
    }


# ══════════════════════════════════════════════════════════════════════════════
# SPA STATIC ASSETS & FALLBACK SERVING
# ══════════════════════════════════════════════════════════════════════════════

if STATIC_DIR and (STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_spa_frontend(full_path: str):
    """
    Catch-all route: serves static assets if found, or falls back to index.html for SPA routing.
    Skips API, docs, openapi.
    """
    if full_path.startswith("api/") or full_path in ("docs", "openapi.json", "redoc"):
        raise HTTPException(status_code=404, detail="Not Found")

    if not STATIC_DIR or not STATIC_DIR.is_dir():
        return JSONResponse(
            status_code=200,
            content={
                "message": "No-Code Agent API is running.",
                "docs": "/docs",
                "frontend": "Frontend dist not found. Run 'python build.py' to build the frontend.",
            },
        )

    target_file = (STATIC_DIR / full_path).resolve()
    # Security check: ensure path is inside STATIC_DIR
    try:
        target_file.relative_to(STATIC_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    if target_file.is_file():
        return FileResponse(target_file)

    index_html = STATIC_DIR / "index.html"
    if index_html.is_file():
        return FileResponse(index_html)

    return JSONResponse(status_code=404, content={"detail": "index.html not found"})
