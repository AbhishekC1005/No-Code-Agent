"""
Versioned Graph JSON Schema for LangGraph visual builder.
Pydantic v2 models and JSON schema export.
"""

from typing import Any, Literal
import json
from pathlib import Path
from pydantic import BaseModel, Field


# ── State Schema ─────────────────────────────────────────────────────────────

class StateField(BaseModel):
    name: str = Field(..., description="Field name in LangGraph TypedDict / state")
    type: str = Field(default="str", description="Type: 'messages', 'str', 'int', 'bool', 'list', 'dict', 'Any'")
    reducer: str = Field(default="overwrite", description="Reducer: 'add_messages', 'overwrite', 'append'")
    default: Any = Field(default=None, description="Default value if not provided")


class StateSchema(BaseModel):
    fields: list[StateField] = Field(
        default_factory=lambda: [
            StateField(name="messages", type="messages", reducer="add_messages", default=[]),
            StateField(name="context", type="list", reducer="overwrite", default=[]),
        ]
    )
    input_fields: list[str] = Field(default_factory=lambda: ["messages"])
    output_fields: list[str] = Field(default_factory=lambda: ["messages"])


# ── Policies ─────────────────────────────────────────────────────────────────

class RetryPolicy(BaseModel):
    max_retries: int = Field(default=0, ge=0)
    delay: float = Field(default=1.0, ge=0.0)
    backoff_factor: float = Field(default=2.0, ge=1.0)


class CachePolicy(BaseModel):
    enabled: bool = False
    ttl: int | None = Field(default=None, description="Time to live in seconds")


class NodePolicy(BaseModel):
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    cache: CachePolicy = Field(default_factory=CachePolicy)
    defer: bool = Field(default=False, description="Defer node execution")
    interrupt_before: bool = Field(default=False, description="Breakpoint before node")
    interrupt_after: bool = Field(default=False, description="Breakpoint after node")


# ── Nodes & Edges ────────────────────────────────────────────────────────────

class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class GraphNode(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(default="agent", description="Node type: 'agent', 'model', 'tool', 'logic', 'trigger', 'output'")
    label: str = Field(default="", description="Human-readable label displayed on canvas")
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    config: dict[str, Any] = Field(default_factory=dict, description="Component configuration")
    policy: NodePolicy = Field(default_factory=NodePolicy)


class GraphEdge(BaseModel):
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node id or START")
    target: str = Field(..., description="Target node id or END")
    kind: Literal["normal", "conditional"] = Field(default="normal")
    condition: dict[str, Any] | None = Field(default=None, description="Condition specification for routing")


# ── Settings ─────────────────────────────────────────────────────────────────

class GraphSettings(BaseModel):
    checkpointer: Literal["sqlite", "memory", "none"] = Field(default="sqlite")
    recursion_limit: int = Field(default=25, ge=1)
    interrupt_before: list[str] = Field(default_factory=list)
    interrupt_after: list[str] = Field(default_factory=list)
    store: dict[str, Any] = Field(default_factory=dict)
    config_fields: list[dict[str, Any]] = Field(default_factory=list)


# ── Root Graph Schema ────────────────────────────────────────────────────────

class GraphSchema(BaseModel):
    schema_version: str = Field(default="1.0", description="SemVer schema version")
    state: StateSchema = Field(default_factory=StateSchema)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    subgraphs: dict[str, Any] = Field(default_factory=dict)
    settings: GraphSettings = Field(default_factory=GraphSettings)


def export_json_schema() -> dict[str, Any]:
    """Return JSON Schema representation of GraphSchema."""
    return GraphSchema.model_json_schema()


def export_json_schema_file(dest_path: str | Path | None = None) -> Path:
    """Export the JSON schema to disk."""
    if dest_path is None:
        dest_path = Path(__file__).resolve().parent / "graph.schema.json"
    p = Path(dest_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(export_json_schema(), indent=2), encoding="utf-8")
    return p
