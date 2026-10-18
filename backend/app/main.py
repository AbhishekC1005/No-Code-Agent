"""
No Code Agent — FastAPI Backend
n8n-style multi-user platform with JWT auth, MongoDB persistence, and workspace CRUD.

Routes:
  POST /api/v1/auth/register   — Create account
  POST /api/v1/auth/login      — Login, get JWT
  GET  /api/v1/auth/me         — Get current user profile

  GET    /api/v1/workspaces             — List user's workspaces
  POST   /api/v1/workspaces             — Create / save workspace
  GET    /api/v1/workspaces/{id}        — Get single workspace
  PUT    /api/v1/workspaces/{id}        — Update workspace
  DELETE /api/v1/workspaces/{id}        — Delete workspace
  POST   /api/v1/workspaces/{id}/compile — Server-side compile to LangGraph Python

  GET  /api/v1/health                   — Health check
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
import zipfile

import os
import json
from bson import ObjectId
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .database import (
    ensure_indexes,
    users_collection,
    workspaces_collection,
    credentials_collection,
    execution_logs_collection,
)
from .models import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceOut,
    ExecuteRequest,
    VaultSave,
)
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)
from .compiler import compile_graph
from .runner import execute_graph
from .vault import encrypt_value, decrypt_value, mask_key


# ── Lifespan: run indexes on startup ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield


app = FastAPI(
    title="No Code Agent Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    # Check duplicate
    existing = await users_collection().find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.now(timezone.utc)
    user_doc = {
        "full_name": req.full_name,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "created_at": now,
    }
    result = await users_collection().insert_one(user_doc)
    user_id = str(result.inserted_id)

    token = create_access_token({"sub": req.email, "uid": user_id})

    return AuthResponse(
        access_token=token,
        user={"id": user_id, "full_name": req.full_name, "email": req.email},
    )


@app.post("/api/v1/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await users_collection().find_one({"email": req.email})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = str(user["_id"])
    token = create_access_token({"sub": req.email, "uid": user_id})

    return AuthResponse(
        access_token=token,
        user={"id": user_id, "full_name": user["full_name"], "email": user["email"]},
    )


@app.get("/api/v1/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["_id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "created_at": user.get("created_at"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# WORKSPACE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

def _workspace_to_out(doc: dict) -> dict:
    """Convert a MongoDB workspace document to the API response shape."""
    return {
        "id": str(doc["_id"]),
        "owner_id": str(doc["owner_id"]),
        "name": doc["name"],
        "nodes": doc.get("nodes", []),
        "edges": doc.get("edges", []),
        "state_schema": doc.get("state_schema", []),
        "eval_rows": doc.get("eval_rows", []),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
        "updated_at": doc.get("updated_at", datetime.now(timezone.utc)),
    }


@app.get("/api/v1/workspaces")
async def list_workspaces(user: dict = Depends(get_current_user_optional)):
    cursor = workspaces_collection().find({"owner_id": user["_id"]}).sort("updated_at", -1)
    docs = await cursor.to_list(length=100)
    return [_workspace_to_out(d) for d in docs]


@app.post("/api/v1/workspaces", status_code=201)
async def create_workspace(
    req: WorkspaceCreate,
    user: dict = Depends(get_current_user_optional),
):
    now = datetime.now(timezone.utc)
    doc = {
        "owner_id": user["_id"],
        "name": req.name,
        "nodes": req.nodes,
        "edges": req.edges,
        "state_schema": req.state_schema,
        "eval_rows": req.eval_rows,
        "created_at": now,
        "updated_at": now,
    }
    result = await workspaces_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return _workspace_to_out(doc)


@app.get("/api/v1/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(get_current_user_optional)):
    try:
        oid = ObjectId(workspace_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    doc = await workspaces_collection().find_one({"_id": oid, "owner_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _workspace_to_out(doc)


@app.put("/api/v1/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    req: WorkspaceUpdate,
    user: dict = Depends(get_current_user_optional),
):
    try:
        oid = ObjectId(workspace_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    for field in ("name", "nodes", "edges", "state_schema", "eval_rows"):
        val = getattr(req, field, None)
        if val is not None:
            update_fields[field] = val

    result = await workspaces_collection().update_one(
        {"_id": oid, "owner_id": user["_id"]},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Workspace not found")

    doc = await workspaces_collection().find_one({"_id": oid})
    return _workspace_to_out(doc)


@app.delete("/api/v1/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str, user: dict = Depends(get_current_user_optional)):
    try:
        oid = ObjectId(workspace_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    result = await workspaces_collection().delete_one({"_id": oid, "owner_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workspace not found")


# ══════════════════════════════════════════════════════════════════════════════
# SERVER-SIDE COMPILE & ZIP DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/workspaces/{workspace_id}/compile")
async def compile_workspace(workspace_id: str, user: dict = Depends(get_current_user_optional)):
    """Compile a workspace's graph into LangGraph Python and return as a ZIP."""
    try:
        oid = ObjectId(workspace_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    doc = await workspaces_collection().find_one({"_id": oid, "owner_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Workspace not found")

    files = compile_graph(
        workspace_name=doc["name"],
        nodes=doc.get("nodes", []),
        edges=doc.get("edges", []),
        state_schema=doc.get("state_schema"),
        eval_rows=doc.get("eval_rows"),
    )

    # Build ZIP in memory
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(f"{doc['name']}/{filename}", content)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{doc["name"]}_langgraph.zip"'},
    )


# ══════════════════════════════════════════════════════════════════════════════
# N8N-STYLE BACKEND EXECUTION & SSE STREAMING
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/execute")
async def execute_agent_workflow(
    req: ExecuteRequest,
    user: dict = Depends(get_current_user_optional),
):
    """
    Execute graph server-side and stream SSE events back to frontend canvas.
    """
    # 1. Fetch credentials for user (or check environment variables)
    cred_doc = await credentials_collection().find_one({"owner_id": user["_id"]})
    credentials: dict[str, str] = {
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "pinecone_key": os.getenv("PINECONE_API_KEY", ""),
    }
    if cred_doc:
        if cred_doc.get("openai_key"):
            credentials["openai_key"] = decrypt_value(cred_doc["openai_key"]) or credentials["openai_key"]
        if cred_doc.get("anthropic_key"):
            credentials["anthropic_key"] = decrypt_value(cred_doc["anthropic_key"]) or credentials["anthropic_key"]
        if cred_doc.get("pinecone_key"):
            credentials["pinecone_key"] = decrypt_value(cred_doc["pinecone_key"]) or credentials["pinecone_key"]

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

        # Log execution to MongoDB for workflow history
        try:
            await execution_logs_collection().insert_one({
                "owner_id": user["_id"],
                "thread_id": req.thread_id,
                "input_message": req.message,
                "final_answer": final_answer,
                "visited_nodes": visited_nodes,
                "total_ms": total_ms,
                "node_traces": node_traces,
                "created_at": datetime.now(timezone.utc),
            })
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


# ══════════════════════════════════════════════════════════════════════════════
# SERVER-SIDE CREDENTIAL VAULT
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/vault")
async def get_vault_credentials(user: dict = Depends(get_current_user_optional)):
    cred_doc = await credentials_collection().find_one({"owner_id": user["_id"]})
    openai_raw = os.getenv("OPENAI_API_KEY", "")
    anthropic_raw = os.getenv("ANTHROPIC_API_KEY", "")
    pinecone_raw = os.getenv("PINECONE_API_KEY", "")

    if cred_doc:
        if cred_doc.get("openai_key"):
            openai_raw = decrypt_value(cred_doc["openai_key"]) or openai_raw
        if cred_doc.get("anthropic_key"):
            anthropic_raw = decrypt_value(cred_doc["anthropic_key"]) or anthropic_raw
        if cred_doc.get("pinecone_key"):
            pinecone_raw = decrypt_value(cred_doc["pinecone_key"]) or pinecone_raw

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
    update_data: dict = {"updated_at": datetime.now(timezone.utc)}
    if req.openai_key:
        update_data["openai_key"] = encrypt_value(req.openai_key)
    if req.anthropic_key:
        update_data["anthropic_key"] = encrypt_value(req.anthropic_key)
    if req.pinecone_key:
        update_data["pinecone_key"] = encrypt_value(req.pinecone_key)

    await credentials_collection().update_one(
        {"owner_id": user["_id"]},
        {"$set": update_data},
        upsert=True,
    )
    return {"status": "saved", "message": "Credentials encrypted and saved to server."}


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "nocode-agent-backend"}

