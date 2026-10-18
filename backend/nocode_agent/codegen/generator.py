"""
LangGraph Code Generator using Jinja2 templates and black formatting.
Generates:
- state.py: TypedDict with Annotated reducers
- nodes.py: Node execution functions with init_chat_model, Command, Send, etc.
- tools.py: Connected langchain_core @tool definitions
- graph.py: StateGraph compilation with checkpointer, policies, and conditional edges
- main.py: FastAPI production REST/SSE service
- langgraph.json: Deployment configuration
- requirements.txt: Pinned dependencies
"""

import ast
import json
import re
from typing import Any
import black
from jinja2 import Environment

from .validator import validate_graph
from .sourcemap import extract_sourcemap


def _sanitize_name(raw: str) -> str:
    """Turn arbitrary label/id into valid Python identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw.lower()).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"node_{cleaned}"
    return cleaned


# ── Jinja2 Templates ─────────────────────────────────────────────────────────

STATE_TEMPLATE = """# State definition for LangGraph workflow
from typing import TypedDict, Annotated, Any, Optional
import operator
from langgraph.graph.message import add_messages


def overwrite(current: Any, update: Any) -> Any:
    \"\"\"Default reducer that replaces existing value.\"\"\"
    return update


class GraphState(TypedDict, total=False):
{% for f in fields %}
{% if f.reducer == "add_messages" or f.type == "messages" %}
    {{ f.name }}: Annotated[list, add_messages]
{% elif f.reducer == "append" or f.reducer == "operator.add" %}
    {{ f.name }}: Annotated[list, operator.add]
{% elif f.reducer == "overwrite" %}
    {{ f.name }}: Annotated[Any, overwrite]
{% else %}
    {{ f.name }}: {{ f.py_type }}
{% endif %}
{% endfor %}
"""

TOOLS_TEMPLATE = """# Tool definitions for LangGraph workflow
import os
import socket
import ipaddress
import urllib.parse
from langchain_core.tools import tool
import httpx
from typing import Any, Optional


def validate_url_safe(url: str):
    \"\"\"SSRF guard: prohibits requests to private, loopback, or reserved IP addresses.\"\"\"
    if os.getenv("ALLOW_LOCAL_TOOL_REQUESTS", "0") == "1":
        return
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError(f"Invalid URL '{url}': hostname is missing.")
    if host.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError(f"SSRF blocked: Requests to loopback host '{host}' are prohibited.")
    try:
        addrinfo = socket.getaddrinfo(host, None)
        for item in addrinfo:
            ip_str = item[4][0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"SSRF blocked: Host '{host}' resolves to restricted IP {ip_str}.")
    except socket.gaierror:
        pass


# Optional MCP tools integration
try:
    from langchain_mcp_adapters.tools import load_mcp_tools
except ImportError:
    load_mcp_tools = None


{% for t in tools %}
{% if t.custom_code %}
{{ t.custom_code }}
{% else %}
@tool
def {{ t.fn_name }}({{ t.args_str }}) -> str:
    \"\"\"{{ t.docstring }}\"\"\"
{% if t.url %}
    try:
        validate_url_safe("{{ t.url }}")
        resp = httpx.request("{{ t.method }}", "{{ t.url }}", timeout=15)
        return resp.text[:500]
    except Exception as exc:
        return f"Tool error: {exc}"
{% else %}
    return f"Executed tool '{{ t.label }}' with input: {query if 'query' in locals() else 'success'}"
{% endif %}
{% endif %}


{% endfor %}
all_tools = [
{% for t in tools %}
    {{ t.fn_name }},
{% endfor %}
]
"""

NODES_TEMPLATE = """# Node functions for LangGraph workflow
import os
import json
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.types import Command, Send
from state import GraphState
{% if has_tools %}
from tools import all_tools
{% endif %}


{% for schema in structured_schemas %}
class {{ schema.name }}(BaseModel):
    \"\"\"{{ schema.description }}\"\"\"
{% for f in schema.fields %}
    {{ f.name }}: {{ f.type }} = Field(default={{ f.default_repr }}, description=\"\"\"{{ f.description }}\"\"\")
{% endfor %}
{% endfor %}


{% for node in nodes %}
# Node: {{ node.label }} (id: {{ node.id }})
{% if node.is_llm %}
async def {{ node.fn_name }}(state: GraphState) -> dict[str, Any]:
    \"\"\"LLM node using {{ node.provider }} model {{ node.model }}.\"\"\"
    messages = state.get("messages", [])
    prompt_template = \"\"\"{{ node.system_prompt }}\"\"\"
    prompt = prompt_template
    for k, v in state.items():
        prompt = prompt.replace("{" + str(k) + "}", str(v) if v is not None else "")
    
{% if node.provider == "anthropic" %}
    if os.getenv("USE_FAKE_LLM", "").lower() in ("1", "true", "yes"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        model = FakeListChatModel(responses=["Test response from {{ node.label }}."])
    else:
        from langchain_anthropic import ChatAnthropic
        model = ChatAnthropic(model_name="{{ node.model }}", temperature={{ node.temperature }})
{% elif node.provider == "ollama" %}
    if os.getenv("USE_FAKE_LLM", "").lower() in ("1", "true", "yes"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        model = FakeListChatModel(responses=["Test response from {{ node.label }}."])
    else:
        from langchain_ollama import ChatOllama
        model = ChatOllama(model="{{ node.model }}", base_url="{{ node.ollama_url }}")
{% else %}
    if os.getenv("USE_FAKE_LLM", "").lower() in ("1", "true", "yes") or "{{ node.provider }}" in ("fake", "mock"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        model = FakeListChatModel(responses=["Test response from {{ node.label }}."])
    else:
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(model="{{ node.model }}", temperature={{ node.temperature }})
{% endif %}
    
{% if node.bind_tools and has_tools %}
    if all_tools and hasattr(model, "bind_tools"):
        model = model.bind_tools(all_tools)
{% endif %}

    full_messages = [SystemMessage(content=prompt)] + list(messages)
{% if node.structured_schema %}
    try:
        if hasattr(model, "with_structured_output"):
            structured_model = model.with_structured_output({{ node.structured_schema.name }})
            res = await structured_model.ainvoke(full_messages)
            out = res.model_dump() if hasattr(res, "model_dump") else (res if isinstance(res, dict) else {"output": str(res)})
            return {
                {% if node.structured_target_field %}
                "{{ node.structured_target_field }}": out,
                {% endif %}
                "messages": [AIMessage(content=json.dumps(out, default=str))],
                "structured_output": out,
            }
        else:
            response = await model.ainvoke(full_messages)
            return {"messages": [response]}
    except Exception as exc:
        fallback = AIMessage(content=f"LLM structured execution error: {exc}")
        return {"messages": [fallback]}
{% else %}
    try:
        response = await model.ainvoke(full_messages)
        return {"messages": [response]}
    except Exception as exc:
        fallback = AIMessage(content=f"LLM execution error: {exc}")
        return {"messages": [fallback]}
{% endif %}

{% elif node.is_command %}
def {{ node.fn_name }}(state: GraphState) -> Command:
    \"\"\"Command node that updates state and specifies dynamic routing target.\"\"\"
{% if node.condition_expr %}
    if {{ node.condition_expr }}:
        return Command(goto="{{ node.command_true }}", update={{ node.update_true }})
    return Command(goto="{{ node.command_false }}", update={{ node.update_false }})
{% else %}
    return Command(goto="{{ node.command_goto }}", update={{ node.update_dict }})
{% endif %}

{% elif node.is_map %}
def {{ node.fn_name }}(state: GraphState) -> Command:
    \"\"\"Map-Reduce Send node that dispatches parallel worker tasks via Command.\"\"\"
    items = state.get("{{ node.items_field }}", ["item_1", "item_2"])
    return Command(goto=[Send("{{ node.send_target }}", {"item": it}) for it in items])

{% elif node.is_human %}
def {{ node.fn_name }}(state: GraphState) -> dict[str, Any]:
    \"\"\"Human-in-the-loop review node calling interrupt().\"\"\"
    from langgraph.types import interrupt
    prompt_msg = \"\"\"{{ node.prompt }}\"\"\"
    review_data = {
        "prompt": prompt_msg,
        "fields": {{ node.fields }},
        "state_summary": {k: v for k, v in state.items() if k != "messages"},
    }
    decision = interrupt(review_data)
    if isinstance(decision, dict):
        return decision
    return {"review_decision": decision, "feedback": decision if isinstance(decision, str) else str(decision)}

{% elif node.is_memory_read %}
def {{ node.fn_name }}(state: GraphState, *, store=None) -> dict[str, Any]:
    \"\"\"Read memory from LangGraph BaseStore.\"\"\"
    key = "{{ node.store_key }}"
    namespace = {{ node.store_namespace }}
    if store:
        try:
            item = store.get(namespace, key)
            val = item.value if item else {}
            return {"{{ node.output_field }}": val}
        except Exception:
            pass
    return {"{{ node.output_field }}": {}}

{% elif node.is_memory_write %}
def {{ node.fn_name }}(state: GraphState, *, store=None) -> dict[str, Any]:
    \"\"\"Write memory to LangGraph BaseStore.\"\"\"
    key = "{{ node.store_key }}"
    namespace = {{ node.store_namespace }}
    val = {k: state.get(k) for k in {{ node.store_fields }} if k in state}
    if store:
        try:
            store.put(namespace, key, val)
        except Exception:
            pass
    return {"store_written": True}

{% else %}
async def {{ node.fn_name }}(state: GraphState) -> dict[str, Any]:
    \"\"\"Standard execution node: {{ node.label }}.\"\"\"
{% if node.updates %}
    return {{ node.updates }}
{% else %}
    return {"context": ["Executed {{ node.label }}"]}
{% endif %}

{% endif %}

{% endfor %}
"""

GRAPH_TEMPLATE = """# LangGraph StateGraph assembly and compilation
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from state import GraphState
import nodes
{% if has_tools %}
import tools
{% endif %}

# ── 1. Create StateGraph Builder ─────────────────────────────────────────────
builder = StateGraph(GraphState)

# ── 2. Add Nodes with Policies ───────────────────────────────────────────────
{% for n in nodes %}
{% if n.is_tool_node %}
builder.add_node("{{ n.name }}", ToolNode(tools.all_tools))
{% else %}
builder.add_node(
    "{{ n.name }}",
    nodes.{{ n.fn_name }},
{% if n.retry_policy %}
    retry_policy={{ n.retry_policy }},
{% endif %}
{% if n.defer %}
    defer=True,
{% endif %}
)
{% endif %}
{% endfor %}

# ── 3. Add Normal and Conditional Edges ──────────────────────────────────────
{% for e in normal_edges %}
# edge:{{ e.id }}
builder.add_edge({{ e.source }}, {{ e.target }})
{% endfor %}

{% for r in routers %}
# Router for conditional edge: {{ r.edge_id }}
def {{ r.fn_name }}(state: GraphState) -> str:
    \"\"\"Router for {{ r.source }}.\"\"\"
    {{ r.router_code }}

builder.add_conditional_edges(
    {{ r.source }},
    {{ r.fn_name }},
    {{ r.path_map }},
)
{% endfor %}

# ── 4. Compile Graph with Checkpointer & Store ────────────────────────────────
{% if store == "sqlite" %}
import os
import sqlite3
from langgraph.store.sqlite import SqliteStore
store_conn = sqlite3.connect(os.environ.get("STORE_DB_PATH", "store.db"), check_same_thread=False, autocommit=True)
store = SqliteStore(store_conn)
store.setup()
{% elif store == "memory" %}
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
{% else %}
store = None
{% endif %}

{% if checkpointer == "sqlite" %}
import os
import sqlite3
import asyncio
from langgraph.checkpoint.sqlite import SqliteSaver

class UniversalSqliteSaver(SqliteSaver):
    \"\"\"Extended SqliteSaver supporting both synchronous and asynchronous LangGraph execution.\"\"\"
    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)
    async def aget(self, config):
        return await asyncio.to_thread(self.get, config)
    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)
    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)
    async def alist(self, config=None, *, filter=None, before=None, limit=None):
        def _get_list():
            return list(self.list(config, filter=filter, before=before, limit=limit))
        items = await asyncio.to_thread(_get_list)
        for item in items:
            yield item
    async def adelete_thread(self, thread_id: str):
        return await asyncio.to_thread(self.delete_thread, thread_id)
    async def adelete_for_runs(self, run_ids):
        return await asyncio.to_thread(self.delete_for_runs, run_ids)

conn = sqlite3.connect(os.environ.get("CHECKPOINTS_DB_PATH", "checkpoints.db"), check_same_thread=False, timeout=30.0)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=30000;")
checkpointer = UniversalSqliteSaver(conn)
checkpointer.setup()
{% elif checkpointer == "memory" %}
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
{% else %}
checkpointer = None
{% endif %}

interrupt_before = {{ interrupt_before or '[]' }}
interrupt_after = {{ interrupt_after or '[]' }}

graph = builder.compile(
{% if checkpointer != "none" and checkpointer is not none %}
    checkpointer=checkpointer,
{% endif %}
{% if store and store != "none" %}
    store=store,
{% endif %}
{% if interrupt_before %}
    interrupt_before=interrupt_before,
{% endif %}
{% if interrupt_after %}
    interrupt_after=interrupt_after,
{% endif %}
)
"""

MAIN_TEMPLATE = """# FastAPI Production REST & Streaming API for LangGraph
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Optional
import json

from graph import graph

app = FastAPI(title="LangGraph Production Service", version="1.0.0")


class RunRequest(BaseModel):
    message: str = "Hello"
    thread_id: str = "default"
    stream: bool = False


@app.get("/health")
async def health():
    return {"status": "ok", "service": "langgraph-service"}


@app.post("/run")
async def run_workflow(req: RunRequest):
    \"\"\"Invoke the compiled LangGraph workflow.\"\"\"
    config = {"configurable": {"thread_id": req.thread_id}}
    initial_input = {"messages": [("user", req.message)]}

    if req.stream:
        async def event_generator():
            async for event in graph.astream(initial_input, config=config):
                yield f"data: {json.dumps(event, default=str)}\\n\\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    result = await graph.ainvoke(initial_input, config=config)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
"""

LANGGRAPH_JSON_TEMPLATE = """{
  "dependencies": ["."],
  "graphs": {
    "workflow": "./graph.py:graph"
  },
  "env": ".env"
}
"""

REQUIREMENTS_TEMPLATE = """langgraph==1.0.5
langgraph-checkpoint-sqlite==3.1.2
langchain-core==1.2.5
fastapi==0.115.8
uvicorn[standard]==0.34.0
httpx==0.28.1
python-dotenv==1.0.1
"""


# ── Precompiled Templates & Constants ───────────────────────────────────────

_ENV = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
_STATE_TMPL = _ENV.from_string(STATE_TEMPLATE)
_TOOLS_TMPL = _ENV.from_string(TOOLS_TEMPLATE)
_NODES_TMPL = _ENV.from_string(NODES_TEMPLATE)
_GRAPH_TMPL = _ENV.from_string(GRAPH_TEMPLATE)
_MAIN_TMPL = _ENV.from_string(MAIN_TEMPLATE)
_LANGGRAPH_JSON_CONTENT = LANGGRAPH_JSON_TEMPLATE
_REQUIREMENTS_CONTENT = REQUIREMENTS_TEMPLATE

_BLACK_MODE = black.Mode()
_PRECOMPILED_MAIN = black.format_str(_MAIN_TMPL.render(), mode=_BLACK_MODE)
_EMPTY_TOOLS = black.format_str(_TOOLS_TMPL.render(tools=[]), mode=_BLACK_MODE)


# ── Code Generator ───────────────────────────────────────────────────────────

class CodeGenerator:
    """Generates LangGraph Python project from Graph JSON schema."""

    def __init__(self):
        self.env = _ENV

    def generate(self, graph_data: dict[str, Any]) -> dict[str, Any]:
        """
        Takes Graph JSON and returns:
        {
          "files": {"state.py", "nodes.py", "tools.py", "graph.py", "main.py", "langgraph.json", "requirements.txt"},
          "sourcemap": { "<node_id>|state|edge:<id>": {"file","start_line","end_line"} },
          "diagnostics": [{"level","node_id","message"}]
        }
        """
        # 1. Run validation
        diagnostics = validate_graph(graph_data)

        # 2. Extract graph components
        state = graph_data.get("state", {})
        raw_fields = state.get("fields", []) if isinstance(state, dict) else []
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        settings = graph_data.get("settings", {})
        subgraphs = graph_data.get("subgraphs", {})

        # Prepare state fields
        type_mapping = {
            "str": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
            "messages": "list",
        }
        processed_fields = []
        for f in raw_fields:
            fname = f.get("name", "messages")
            ftype = f.get("type", "messages")
            processed_fields.append({
                "name": fname,
                "type": ftype,
                "py_type": type_mapping.get(ftype, "Any"),
                "reducer": f.get("reducer", "add_messages" if ftype == "messages" else "overwrite"),
                "default": f.get("default"),
            })

        if not processed_fields:
            processed_fields = [{
                "name": "messages",
                "type": "messages",
                "py_type": "list",
                "reducer": "add_messages",
                "default": [],
            }]

        # Prepare node identifiers and functions
        node_to_fn: dict[str, str] = {}
        processed_nodes = []
        tools_list = []
        has_tools = False

        structured_schemas = []

        for n in nodes:
            nid = n.get("id", "n")
            ntype = n.get("type", "agent")
            if nid.upper() in ("START", "__START__", "END", "__END__") or ntype in ("triggers", "trigger", "output"):
                continue

            label = n.get("label") or nid
            fn_name = f"{_sanitize_name(label)}_{_sanitize_name(nid)}"
            node_to_fn[nid] = fn_name

            cfg = n.get("config", {})
            policy = n.get("policy", {})

            is_human = bool(ntype in ("human", "human_review", "hitl") or cfg.get("is_human"))
            is_memory_read = bool(ntype in ("memory_read", "store_read") or cfg.get("is_memory_read"))
            is_memory_write = bool(ntype in ("memory_write", "store_write") or cfg.get("is_memory_write"))
            is_command = bool(cfg.get("is_command") or "command" in ntype.lower())
            is_map = bool(cfg.get("is_map") or "map" in ntype.lower())
            is_tool = ntype in ("tool", "tools")
            is_llm = ntype in ("model", "models", "agent", "agents", "llm", "llms") and not is_command and not is_map and not is_human and not is_memory_read and not is_memory_write

            if is_tool:
                has_tools = True
                tools_list.append({
                    "fn_name": fn_name,
                    "label": label,
                    "docstring": cfg.get("description", f"Execute {label}"),
                    "args_str": "query: str = ''",
                    "url": cfg.get("url"),
                    "method": cfg.get("method", "GET"),
                    "custom_code": cfg.get("code") or cfg.get("custom_code"),
                })

            # Check for structured output configuration
            structured_cfg = cfg.get("structured_output") or cfg.get("structuredOutput")
            node_schema = None
            if structured_cfg and isinstance(structured_cfg, dict):
                s_name = _sanitize_name(structured_cfg.get("schema_name") or f"{fn_name}_output").capitalize()
                s_fields = []
                for sf in structured_cfg.get("fields", []):
                    s_fields.append({
                        "name": _sanitize_name(sf.get("name", "field")),
                        "type": type_mapping.get(sf.get("type", "str"), "str"),
                        "default_repr": repr(sf.get("default")) if "default" in sf and sf["default"] is not None else "...",
                        "description": sf.get("description", ""),
                    })
                if not s_fields:
                    s_fields = [{"name": "response", "type": "str", "default_repr": "...", "description": "Response content"}]
                node_schema = {
                    "name": s_name,
                    "description": structured_cfg.get("description", f"Structured output model for {label}"),
                    "fields": s_fields,
                }
                structured_schemas.append(node_schema)

            bind_tools = bool(cfg.get("bind_tools") or cfg.get("bindTools") or cfg.get("tools"))

            provider = (cfg.get("llmProvider") or cfg.get("provider") or "openai").lower()
            model = cfg.get("model") or ("gpt-4o-mini" if provider == "openai" else ("claude-3-5-sonnet-20241022" if provider == "anthropic" else "llama3"))

            processed_nodes.append({
                "id": nid,
                "name": nid,
                "label": label,
                "fn_name": fn_name,
                "type": ntype,
                "is_llm": is_llm,
                "is_human": is_human,
                "prompt": cfg.get("prompt", "Please review and approve this action."),
                "fields": json.dumps(cfg.get("fields", [])),
                "is_memory_read": is_memory_read,
                "is_memory_write": is_memory_write,
                "store_key": cfg.get("key", "user_prefs"),
                "store_namespace": repr(tuple(cfg.get("namespace", ["memories"]))),
                "output_field": cfg.get("output_field", "memory"),
                "store_fields": repr(cfg.get("fields", ["context", "messages"])),
                "is_tool_node": is_tool and bool(cfg.get("use_tool_node")),
                "is_command": is_command,
                "is_map": is_map,
                "provider": provider,
                "model": model,
                "temperature": float(cfg.get("temperature", 0.0)),
                "system_prompt": cfg.get("systemPrompt", "You are a helpful assistant."),
                "ollama_url": cfg.get("ollamaBaseUrl", "http://localhost:11434"),
                "bind_tools": bind_tools,
                "structured_schema": node_schema,
                "structured_target_field": cfg.get("target_field") or cfg.get("output_field"),
                "condition_expr": cfg.get("condition"),
                "command_true": cfg.get("goto_true", "END"),
                "command_false": cfg.get("goto_false", "agent"),
                "update_true": json.dumps(cfg.get("update_true", {})),
                "update_false": json.dumps(cfg.get("update_false", {})),
                "command_goto": cfg.get("goto", "END"),
                "update_dict": json.dumps(cfg.get("update", {})),
                "goto_targets": '"' + '", "'.join(list(node_to_fn.keys()) + ["END"]) + '"',
                "items_field": cfg.get("items_field", "items"),
                "send_target": cfg.get("send_target", "worker"),
                "updates": json.dumps(
                    cfg.get("updates")
                    or (
                        (lambda c: ast.literal_eval(c[7:].strip()) if c.startswith("return ") else {})(str(cfg.get("code", "")).strip())
                        if "return " in str(cfg.get("code", "")) else {}
                    )
                    or {"context": [f"Executed {label}"]}
                ),
                "retry_policy": None,
                "defer": policy.get("defer", False),
            })

        # Edges and conditional routers
        normal_edges = []
        routers = []

        for e in edges:
            eid = e.get("id", "e")
            raw_src = e.get("source", "START")
            raw_tgt = e.get("target", "END")

            src_is_start = raw_src.upper() in ("START", "__START__") or any(
                n.get("id") == raw_src and n.get("type") in ("triggers", "trigger") for n in nodes
            )
            tgt_is_end = raw_tgt.upper() in ("END", "__END__") or any(
                n.get("id") == raw_tgt and n.get("type") == "output" for n in nodes
            )

            src_repr = "START" if src_is_start else f'"{raw_src}"'
            tgt_repr = "END" if tgt_is_end else f'"{raw_tgt}"'

            if e.get("kind") == "conditional":
                cond = e.get("condition") or {}
                router_fn = f"route_{_sanitize_name(raw_src)}_{_sanitize_name(eid)}"
                branches = cond.get("branches") or cond.get("path_map") or {"continue": raw_tgt, "end": "END"}

                path_map_dict = {}
                for k, v in branches.items():
                    v_repr = "END" if v.upper() in ("END", "__END__") or any(
                        n.get("id") == v and n.get("type") == "output" for n in nodes
                    ) else v
                    path_map_dict[k] = v_repr

                router_code = (
                    f"if state.get('retry_count', 0) > 2:\n"
                    f"        return 'end'\n"
                    f"    return 'continue'"
                ) if not cond.get("code") else cond["code"]

                path_map_str = "{" + ", ".join(f'"{k}": {v if v in ("END", "__end__") else repr(v)}' for k, v in path_map_dict.items()) + "}"
                routers.append({
                    "edge_id": eid,
                    "source": src_repr,
                    "fn_name": router_fn,
                    "router_code": router_code,
                    "path_map": path_map_str,
                })
            else:
                normal_edges.append({
                    "id": eid,
                    "source": src_repr,
                    "target": tgt_repr,
                })

        # Render files using precompiled templates
        state_code = _STATE_TMPL.render(fields=processed_fields)
        tools_code = _TOOLS_TMPL.render(tools=tools_list) if tools_list else _EMPTY_TOOLS
        # Configure store and merge breakpoints
        store_cfg = settings.get("store")
        if isinstance(store_cfg, dict):
            store_type = store_cfg.get("type", "sqlite" if any(n["is_memory_read"] or n["is_memory_write"] for n in processed_nodes) else "none")
        elif isinstance(store_cfg, str):
            store_type = store_cfg
        elif any(n["is_memory_read"] or n["is_memory_write"] for n in processed_nodes):
            store_type = "sqlite"
        else:
            store_type = "none"

        interrupt_before = list(settings.get("interrupt_before", []))
        interrupt_after = list(settings.get("interrupt_after", []))
        for n in nodes:
            nid = n.get("id")
            pol = n.get("policy", {})
            if pol.get("interrupt_before") and nid not in interrupt_before:
                interrupt_before.append(nid)
            if pol.get("interrupt_after") and nid not in interrupt_after:
                interrupt_after.append(nid)

        nodes_code = _NODES_TMPL.render(nodes=processed_nodes, has_tools=has_tools, structured_schemas=structured_schemas)
        graph_code = _GRAPH_TMPL.render(
            nodes=processed_nodes,
            normal_edges=normal_edges,
            routers=routers,
            has_tools=has_tools,
            checkpointer=settings.get("checkpointer", "sqlite"),
            store=store_type,
            interrupt_before=json.dumps(interrupt_before) if interrupt_before else None,
            interrupt_after=json.dumps(interrupt_after) if interrupt_after else None,
        )

        rendered_files = {
            "state.py": state_code,
            "tools.py": tools_code,
            "nodes.py": nodes_code,
            "graph.py": graph_code,
            "main.py": _PRECOMPILED_MAIN,
            "langgraph.json": _LANGGRAPH_JSON_CONTENT,
            "requirements.txt": _REQUIREMENTS_CONTENT,
        }

        # Check if custom unstructured code was supplied
        has_custom_code = any(
            n.get("config", {}).get("code") or n.get("config", {}).get("custom_code")
            for n in nodes
        ) or any(
            (e.get("condition") or {}).get("code")
            for e in edges
        )
        should_run_black = has_custom_code or len(nodes) <= 15

        # Format Python files with black and verify syntax with ast.parse
        formatted_files: dict[str, str] = {}
        for fname, content in rendered_files.items():
            if fname in ("main.py",):
                formatted_files[fname] = content
            elif fname == "tools.py" and not tools_list:
                formatted_files[fname] = content
            elif fname.endswith(".py"):
                if should_run_black:
                    try:
                        formatted = black.format_str(content, mode=_BLACK_MODE)
                    except Exception:
                        formatted = content
                else:
                    formatted = content

                # Verify syntax with ast.parse
                try:
                    ast.parse(formatted)
                except Exception as exc:
                    diagnostics.append({
                        "level": "error",
                        "node_id": None,
                        "message": f"Syntax error in generated {fname}: {exc}",
                    })

                formatted_files[fname] = formatted
            else:
                formatted_files[fname] = content

        # Compute sourcemap
        sourcemap = extract_sourcemap(
            files=formatted_files,
            nodes=nodes,
            edges=edges,
            node_to_fn_map=node_to_fn,
        )

        return {
            "files": formatted_files,
            "sourcemap": sourcemap,
            "diagnostics": diagnostics,
        }


def generate_langgraph_project(graph_data: dict[str, Any]) -> dict[str, Any]:
    """Top-level helper function to generate LangGraph project from Graph JSON."""
    generator = CodeGenerator()
    return generator.generate(graph_data)
