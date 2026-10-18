"""
Server-side Python code compiler.
Mirrors the frontend pythonCompiler.ts logic so the backend can also
generate export ZIPs and serve compiled code via API.
"""

import re
import json
from typing import Any


def _sanitize_id(raw: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]", "_", raw.lower()).strip("_")
    return cleaned or "node_fn"


def compile_graph(
    workspace_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    state_schema: list[dict[str, Any]] | None = None,
    eval_rows: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """
    Compile a visual graph (nodes + edges) into production LangGraph Python files.
    Returns a dict of filename → file content.
    """
    state_schema = state_schema or [
        {"key": "messages", "type": "messages", "reducer": "add_messages"},
        {"key": "context", "type": "list", "reducer": "overwrite"},
        {"key": "retry_count", "type": "int", "reducer": "overwrite"},
    ]
    eval_rows = eval_rows or []

    # ── 1. State fields ─────────────────────────────────────────────────────
    type_map = {"str": "str", "int": "int", "bool": "bool", "list": "list", "dict": "dict"}
    state_fields: list[str] = []
    for f in state_schema:
        if f.get("reducer") == "add_messages" or f.get("type") == "messages":
            state_fields.append(f"    {f['key']}: Annotated[list, add_messages]")
        elif f.get("reducer") == "append":
            state_fields.append(f"    {f['key']}: Annotated[list, operator.add]")
        else:
            py_type = type_map.get(f.get("type", ""), "Any")
            state_fields.append(f"    {f['key']}: {py_type}")

    # ── 2. Node function names ───────────────────────────────────────────────
    node_fn_map: dict[str, str] = {}
    for n in nodes:
        label = n.get("data", {}).get("label", n["id"])
        node_fn_map[n["id"]] = f"{_sanitize_id(label)}_{_sanitize_id(n['id'])}"

    node_defs: list[str] = []
    builder_add: list[str] = []
    memory_provider = "memory"

    for node in nodes:
        data = node.get("data", {})
        cat = data.get("category", "agents")
        cfg = data.get("config", {})
        fn = node_fn_map[node["id"]]

        if cat in ("triggers", "output"):
            continue
        if cat == "memory":
            memory_provider = cfg.get("provider", "postgres")
            continue

        builder_add.append(f'builder.add_node("{fn}", {fn})')

        if cat in ("models", "agents"):
            provider = cfg.get("llmProvider", "openai")
            model = cfg.get("model", "gpt-4o-mini")
            sys_prompt = cfg.get("systemPrompt", "You are an autonomous LangGraph agent.")
            temp = cfg.get("temperature", 0)
            llm_init = (
                f'ChatAnthropic(model="{model}", temperature={temp})'
                if provider == "anthropic"
                else f'ChatOpenAI(model="{model}", temperature={temp})'
            )
            node_defs.append(
                f'async def {fn}(state: AgentState) -> dict:\n'
                f'    """[{cat.upper()}] {data.get("label", "")}"""\n'
                f'    llm = {llm_init}\n'
                f'    context_docs = state.get("context", [])\n'
                f'    context_str = "\\n".join(context_docs) if context_docs else ""\n'
                f'    sys_msg = {json.dumps(sys_prompt)} + (f"\\n\\nContext:\\n{{context_str}}" if context_str else "")\n'
                f'    messages = [{{"role": "system", "content": sys_msg}}] + state.get("messages", [])\n'
                f'    response = await llm.ainvoke(messages)\n'
                f'    return {{"messages": [response]}}\n'
            )
        elif cat == "knowledge":
            db_type = cfg.get("provider", "Pinecone")
            index_name = cfg.get("indexName", "agent-knowledge-index")
            top_k = cfg.get("topK", 4)
            if "pinecone" in db_type.lower():
                store_fn = "get_pinecone_store"
            elif "mongo" in db_type.lower():
                store_fn = "get_mongodb_store"
            else:
                store_fn = "get_pgvector_store"
            node_defs.append(
                f'async def {fn}(state: AgentState) -> dict:\n'
                f'    """[KNOWLEDGE] {data.get("label", "")}"""\n'
                f'    query = state["messages"][-1].content if state.get("messages") else ""\n'
                f'    vectorstore = {store_fn}("{index_name}")\n'
                f'    docs = await vectorstore.asimilarity_search(query, k={top_k})\n'
                f'    return {{"context": [d.page_content for d in docs]}}\n'
            )
        elif cat == "tools":
            url = cfg.get("url", "https://api.example.com/v1/action")
            method = (cfg.get("method", "POST")).upper()
            custom = cfg.get("customPythonCode", "")
            if custom.strip():
                indented = "\n".join("    " + line for line in custom.split("\n"))
                node_defs.append(
                    f'async def {fn}(state: AgentState) -> dict:\n'
                    f'    """[CUSTOM TOOL] {data.get("label", "")}"""\n'
                    f'{indented}\n'
                )
            else:
                node_defs.append(
                    f'async def {fn}(state: AgentState) -> dict:\n'
                    f'    """[HTTP TOOL] {data.get("label", "")} -> {method} {url}"""\n'
                    f'    async with httpx.AsyncClient(timeout=15.0) as client:\n'
                    f'        resp = await client.request("{method}", "{url}", json={{"state_summary": str(state.get("messages", [])[-1:])}})\n'
                    f'        return {{"messages": [{{"role": "assistant", "content": f"Tool Response ({{resp.status_code}}): {{resp.text[:300]}}"}}]}}\n'
                )
        elif cat == "logic":
            cond_field = cfg.get("conditionField", "retry_count")
            human = cfg.get("humanApproval", False)
            if human:
                body = '    human_decision = interrupt({"question": "Approve agent execution?", "state": state})\n    return {"approved": bool(human_decision)}'
            else:
                body = f'    return {{"{cond_field}": state.get("{cond_field}", 0)}}'
            node_defs.append(
                f'async def {fn}(state: AgentState) -> dict:\n'
                f'    """[LOGIC] {data.get("label", "")}"""\n'
                f'{body}\n'
            )
        else:
            node_defs.append(
                f'async def {fn}(state: AgentState) -> dict:\n'
                f'    """[PLUGIN] {data.get("label", "")}"""\n'
                f'    return {{}}\n'
            )

    # ── 3. Edges ─────────────────────────────────────────────────────────────
    edge_lines: list[str] = []
    nodes_by_id = {n["id"]: n for n in nodes}
    for edge in edges:
        src = nodes_by_id.get(edge.get("source"))
        tgt = nodes_by_id.get(edge.get("target"))
        if not src or not tgt:
            continue
        src_cat = src.get("data", {}).get("category")
        tgt_cat = tgt.get("data", {}).get("category")
        if src_cat == "memory" or tgt_cat == "memory":
            continue
        src_ref = "START" if src_cat == "triggers" else f'"{node_fn_map[src["id"]]}"'
        tgt_ref = "END" if tgt_cat == "output" else f'"{node_fn_map[tgt["id"]]}"'
        edge_lines.append(f"builder.add_edge({src_ref}, {tgt_ref})")

    # ── 4. Assemble files ────────────────────────────────────────────────────
    mp = memory_provider.lower()

    connections_py = f'''"""
Database, Vector Store & Checkpointer Adapters (Auto-generated)
"""
import os
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_postgres import PGVector
from pymongo import MongoClient
from langgraph.checkpoint.memory import MemorySaver

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

def get_pinecone_store(index_name: str):
    return PineconeVectorStore(index_name=index_name, embedding=embeddings)

def get_mongodb_store(collection_name: str):
    client = MongoClient(os.environ["MONGODB_URI"])
    collection = client["langgraph_db"][collection_name]
    return MongoDBAtlasVectorSearch(collection=collection, embedding=embeddings)

def get_pgvector_store(collection_name: str):
    return PGVector(embeddings=embeddings, collection_name=collection_name, connection=os.environ["POSTGRES_URL"], use_jsonb=True)

def get_checkpointer():
    provider = "{mp}"
    if "postgres" in provider and os.getenv("POSTGRES_URL"):
        from langgraph.checkpoint.postgres import PostgresSaver
        return PostgresSaver.from_conn_string(os.environ["POSTGRES_URL"])
    if "mongo" in provider and os.getenv("MONGODB_URI"):
        from langgraph.checkpoint.mongodb import MongoDBSaver
        client = MongoClient(os.environ["MONGODB_URI"])
        return MongoDBSaver(client)
    return MemorySaver()
'''

    graph_py = f'''"""
Auto-Compiled LangGraph StateGraph
Workspace: {workspace_name}
"""
import operator
import httpx
from typing import Annotated, TypedDict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from connections import get_pinecone_store, get_mongodb_store, get_pgvector_store, get_checkpointer

class AgentState(TypedDict, total=False):
{chr(10).join(state_fields)}

{chr(10).join(node_defs)}

builder = StateGraph(AgentState)
{chr(10).join(builder_add)}

{chr(10).join(edge_lines)}

checkpointer = get_checkpointer()
graph = builder.compile(checkpointer=checkpointer)
'''

    main_py = f'''"""
Production REST API Microservice for {workspace_name}
"""
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from graph import graph

app = FastAPI(title="{workspace_name} - LangGraph API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class AgentInvokeRequest(BaseModel):
    message: str
    metadata: Optional[Dict[str, Any]] = None

@app.post("/v1/threads/{{thread_id}}/invoke")
async def invoke_thread(thread_id: str, req: AgentInvokeRequest):
    config = {{"configurable": {{"thread_id": thread_id}}}}
    result = await graph.ainvoke({{"messages": [{{"role": "user", "content": req.message}}]}}, config=config)
    last_msg = result["messages"][-1].content if result.get("messages") else ""
    return {{"thread_id": thread_id, "output": last_msg, "context": result.get("context", [])}}

@app.post("/v1/threads/{{thread_id}}/stream")
async def stream_thread(thread_id: str, req: AgentInvokeRequest):
    config = {{"configurable": {{"thread_id": thread_id}}}}
    async def event_stream():
        async for event in graph.astream_events({{"messages": [{{"role": "user", "content": req.message}}]}}, config=config, version="v2"):
            kind = event["event"]
            if kind == "on_chain_start":
                yield f"data: {{json.dumps({{'type': 'node_start', 'node': event['name']}})}}\\n\\n"
            elif kind == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    yield f"data: {{json.dumps({{'type': 'token', 'content': token}})}}\\n\\n"
        yield f"data: {{json.dumps({{'type': 'done'}})}}\\n\\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
'''

    test_evals_py = f'''"""
Automated LangGraph Evaluation & Trajectory Harness
Run via: pytest test_evals.py -v
"""
import time
import pytest
from graph import graph

EVAL_SUITE = {json.dumps(eval_rows, indent=4)}

@pytest.mark.asyncio
@pytest.mark.parametrize("case", EVAL_SUITE)
async def test_langgraph_trajectory_and_output(case):
    t0 = time.perf_counter()
    config = {{"configurable": {{"thread_id": f"eval-{{case[\'id\']}}"}}}}
    executed_nodes = []
    async for event in graph.astream_events(
        {{"messages": [{{"role": "user", "content": case["input"]}}]}},
        config=config, version="v2",
    ):
        if event["event"] == "on_chain_start" and event["name"] not in ("LangGraph", "__start__"):
            executed_nodes.append(event["name"])
    latency_ms = (time.perf_counter() - t0) * 1000
    assert latency_ms <= case.get("maxLatencyMs", 15000)
    state = await graph.aget_state(config)
    final_msg = str(state.values.get("messages", [""])[-1]).lower()
    if case.get("expectedKeyword"):
        assert case["expectedKeyword"].lower() in final_msg
'''

    requirements_txt = "\n".join([
        "langgraph>=0.2.38",
        "langchain-openai>=0.2.3",
        "langchain-anthropic>=0.2.3",
        "langchain-pinecone>=0.2.0",
        "langchain-mongodb>=0.2.0",
        "langchain-postgres>=0.0.12",
        "langgraph-checkpoint-postgres>=2.0.2",
        "langgraph-checkpoint-mongodb>=0.1.0",
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.6",
        "httpx>=0.27.2",
        "pymongo>=4.9.0",
        "pytest>=8.3.0",
        "pytest-asyncio>=0.24.0",
    ])

    dockerfile = (
        'FROM python:3.12-slim\n'
        'WORKDIR /app\n'
        'COPY requirements.txt .\n'
        'RUN pip install --no-cache-dir -r requirements.txt\n'
        'COPY . .\n'
        'EXPOSE 8080\n'
        'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]\n'
    )

    env_example = "\n".join([
        "OPENAI_API_KEY=sk-...",
        "ANTHROPIC_API_KEY=sk-ant-...",
        "POSTGRES_URL=postgresql://user:pass@localhost:5432/agent_db",
        "MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/",
        "PINECONE_API_KEY=pcsk_...",
    ])

    return {
        "graph.py": graph_py,
        "connections.py": connections_py,
        "main.py": main_py,
        "test_evals.py": test_evals_py,
        "requirements.txt": requirements_txt,
        "Dockerfile": dockerfile,
        ".env.example": env_example,
    }
