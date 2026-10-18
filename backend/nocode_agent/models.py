"""
Pydantic models for request / response schemas.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    created_at: datetime


# ── Workspaces ───────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    state_schema: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    nodes: Optional[list[dict[str, Any]]] = None
    edges: Optional[list[dict[str, Any]]] = None
    state_schema: Optional[list[dict[str, Any]]] = None
    eval_rows: Optional[list[dict[str, Any]]] = None


class WorkspaceOut(BaseModel):
    id: str
    owner_id: str
    name: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    state_schema: list[dict[str, Any]]
    eval_rows: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


# ── Execution ────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    """Sent by the frontend to run the current canvas graph on the backend."""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    message: str
    thread_id: str = "default"


class RunWorkflowRequest(BaseModel):
    """Request payload for running generated LangGraph in subprocess."""
    workflow_id: str = "default"
    graph: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    input: Optional[dict[str, Any]] = None
    thread_id: str = "default"
    checkpoint_id: Optional[str] = None
    resume: Optional[Any] = None
    stream_mode: str = "updates"
    timeout_seconds: float = 60.0


class UpdateStateRequest(BaseModel):
    """Payload to update/edit state for a thread checkpoint (time travel)."""
    values: dict[str, Any]
    as_node: Optional[str] = None
    checkpoint_id: Optional[str] = None


class ForkThreadRequest(BaseModel):
    """Payload to fork a thread from a given checkpoint."""
    from_checkpoint_id: str
    new_thread_id: Optional[str] = None


# ── Vault ────────────────────────────────────────────────────────────────────

class VaultSave(BaseModel):
    """API keys to store server-side (encrypted at rest)."""
    openai_key: str = ""
    anthropic_key: str = ""
    pinecone_key: str = ""
