"""
Data models for the n8n-style execution engine.
Items are represented as list of dicts: [{"json": {...}}, ...]
"""

from typing import Any, Union
from pydantic import BaseModel, Field


def make_item(json_data: Any) -> dict[str, Any]:
    """Wraps arbitrary data in the canonical n8n item shape: {'json': {...}}."""
    if isinstance(json_data, dict) and "json" in json_data and isinstance(json_data["json"], dict):
        return json_data
    if isinstance(json_data, dict):
        return {"json": json_data}
    return {"json": {"value": json_data}}


def ensure_item_list(items: Any) -> list[dict[str, Any]]:
    """Ensures input is a valid list of n8n items."""
    if items is None:
        return [make_item({})]
    if isinstance(items, list):
        if not items:
            return [make_item({})]
        return [make_item(it) for it in items]
    return [make_item(items)]


class NodeOutput(BaseModel):
    """
    Output of a node execution.
    ports: mapping of port index/name to list of items.
    port 0: main / true / loop output
    port 1: false / done output
    'error': error branch output
    """
    ports: dict[Union[int, str], list[dict[str, Any]]] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: int = 0
    tokens: list[str] = Field(default_factory=list)

    def get_items(self, port: Union[int, str] = 0) -> list[dict[str, Any]]:
        return self.ports.get(port) or self.ports.get(str(port)) or []

    def set_items(self, port: Union[int, str], items: list[dict[str, Any]]):
        self.ports[port] = items


class SingleNodeRunRequest(BaseModel):
    """Request schema for running a single node with provided inputs."""
    node: dict[str, Any]
    input_items: list[dict[str, Any]] = Field(default_factory=lambda: [make_item({})])
    connected_tools: list[dict[str, Any]] = Field(default_factory=list)
    credentials: dict[str, str] = Field(default_factory=dict)
    node_outputs: dict[str, Any] = Field(default_factory=dict)


class RerunFromRequest(BaseModel):
    """Request schema for rerunning workflow starting from a specific node."""
    start_node_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    pinned_input_items: list[dict[str, Any]] = Field(default_factory=lambda: [make_item({})])
    credentials: dict[str, str] = Field(default_factory=dict)
    thread_id: str = "default"
