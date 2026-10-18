"""
Pydantic models for request/response schemas and MongoDB document shapes.
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


# ── Vault ────────────────────────────────────────────────────────────────────

class VaultSave(BaseModel):
    """API keys to store server-side (encrypted at rest)."""
    openai_key: str = ""
    anthropic_key: str = ""
    pinecone_key: str = ""
