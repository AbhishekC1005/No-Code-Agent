"""
Re-export n8n-style runner from engine package for backward-compatibility.
"""

from .engine.runner import execute_graph, execute_single_node
from .engine.models import make_item, ensure_item_list, NodeOutput

__all__ = [
    "execute_graph",
    "execute_single_node",
    "make_item",
    "ensure_item_list",
    "NodeOutput",
]
