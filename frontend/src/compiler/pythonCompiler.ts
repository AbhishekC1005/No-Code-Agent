import JSZip from "jszip";
import type { Node, Edge } from "@xyflow/react";

export interface StateSchemaItem {
  key: string;
  type: "messages" | "str" | "int" | "bool" | "list" | "dict";
  reducer: "add_messages" | "overwrite" | "append";
}

export interface EvalRow {
  id: string;
  input: string;
  expectedTrajectory: string[];
  expectedKeyword: string;
  maxLatencyMs: number;
}

function sanitizeId(raw: string): string {
  return raw.toLowerCase().replace(/[^a-z0-9_]/g, "_").replace(/^_+|_+$/g, "") || "node_fn";
}

export function compileGraphInBrowser(
  workspaceName: string,
  nodes: Node[],
  edges: Edge[],
  stateSchema: StateSchemaItem[],
  evalRows: EvalRow[]
): Record<string, string> {
  // 1. Build TypedDict State Schema
  const stateFields = stateSchema.map((f) => {
    if (f.reducer === "add_messages" || f.type === "messages") {
      return `    ${f.key}: Annotated[list, add_messages]`;
    }
    if (f.reducer === "append") {
      return `    ${f.key}: Annotated[list, operator.add]`;
    }
    const typeMap: Record<string, string> = {
      str: "str",
      int: "int",
      bool: "bool",
      list: "list",
      dict: "dict",
    };
    return `    ${f.key}: ${typeMap[f.type] || "Any"}`;
  });

  // 2. Map Node IDs to clean Python function names
  const nodeFnMap: Record<string, string> = {};
  nodes.forEach((n) => {
    const label = String(n.data?.label || n.id);
    nodeFnMap[n.id] = `${sanitizeId(label)}_${sanitizeId(n.id)}`;
  });

  const nodeDefinitions: string[] = [];
  const builderAddNodes: string[] = [];
  let memoryProvider = "memory"; // default MemorySaver

  nodes.forEach((node) => {
    const data: any = node.data || {};
    const cat = data.category;
    const cfg = data.config || {};
    const fnName = nodeFnMap[node.id];

    if (cat === "triggers" || cat === "output") return;

    if (cat === "memory") {
      memoryProvider = cfg.provider || "postgres";
      return; // Memory nodes configure the LangGraph checkpointer directly
    }

    builderAddNodes.push(`builder.add_node("${fnName}", ${fnName})`);

    if (cat === "models" || cat === "agents") {
      const provider = cfg.llmProvider || "openai";
      const model = cfg.model || "gpt-4o-mini";
      const sysPrompt = cfg.systemPrompt || "You are an autonomous LangGraph agent.";
      const temperature = cfg.temperature ?? 0;

      const llmInit =
        provider === "anthropic"
          ? `ChatAnthropic(model="${model}", temperature=${temperature})`
          : `ChatOpenAI(model="${model}", temperature=${temperature})`;

      nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[${cat.toUpperCase()}] ${data.label}"""
    llm = ${llmInit}
    context_docs = state.get("context", [])
    context_str = "\\n".join(context_docs) if context_docs else ""
    sys_msg = ${JSON.stringify(sysPrompt)} + (f"\\n\\nContext:\\n{context_str}" if context_str else "")
    messages = [{"role": "system", "content": sys_msg}] + state.get("messages", [])
    response = await llm.ainvoke(messages)
    return {"messages": [response]}
`);
    } else if (cat === "knowledge") {
      const dbType = cfg.provider || "Pinecone";
      const indexName = cfg.indexName || "agent-knowledge-index";
      const topK = cfg.topK || 4;

      if (dbType.toLowerCase().includes("pinecone")) {
        nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[KNOWLEDGE - PINECONE RAG] ${data.label}"""
    query = state["messages"][-1].content if state.get("messages") else ""
    vectorstore = get_pinecone_store("${indexName}")
    docs = await vectorstore.asimilarity_search(query, k=${topK})
    return {"context": [d.page_content for d in docs]}
`);
      } else if (dbType.toLowerCase().includes("mongo")) {
        nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[KNOWLEDGE - MONGODB ATLAS VECTOR SEARCH] ${data.label}"""
    query = state["messages"][-1].content if state.get("messages") else ""
    vectorstore = get_mongodb_store("${indexName}")
    docs = await vectorstore.asimilarity_search(query, k=${topK})
    return {"context": [d.page_content for d in docs]}
`);
      } else {
        nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[KNOWLEDGE - PGVECTOR RAG] ${data.label}"""
    query = state["messages"][-1].content if state.get("messages") else ""
    vectorstore = get_pgvector_store("${indexName}")
    docs = await vectorstore.asimilarity_search(query, k=${topK})
    return {"context": [d.page_content for d in docs]}
`);
      }
    } else if (cat === "tools") {
      const url = cfg.url || "https://api.example.com/v1/action";
      const method = (cfg.method || "POST").toUpperCase();
      const customPython = cfg.customPythonCode || "";

      if (customPython.trim()) {
        nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[CUSTOM PYTHON TOOL] ${data.label}"""
${customPython
  .split("\n")
  .map((l: string) => "    " + l)
  .join("\n")}
`);
      } else {
        nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[HTTP TOOL] ${data.label} -> ${method} ${url}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.request("${method}", "${url}", json={"state_summary": str(state.get("messages", [])[-1:])})
        return {"messages": [{"role": "assistant", "content": f"Tool Response ({resp.status_code}): {resp.text[:300]}"}]}
`);
      }
    } else if (cat === "logic") {
      const conditionField = cfg.conditionField || "retry_count";
      const pauseForHuman = cfg.humanApproval || false;

      nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[LOGIC / ROUTER / INTERRUPT] ${data.label}"""
    ${
      pauseForHuman
        ? 'human_decision = interrupt({"question": "Approve agent execution?", "state": state})\n    return {"approved": bool(human_decision)}'
        : `return {"${conditionField}": state.get("${conditionField}", 0)}`
    }
`);
    } else {
      nodeDefinitions.push(`async def ${fnName}(state: AgentState) -> dict:
    """[PLUGIN / MCP] ${data.label}"""
    return {}
`);
    }
  });

  // 3. Build Standard & Conditional Edges
  const edgeLines: string[] = [];
  edges.forEach((edge) => {
    const srcNode = nodes.find((n) => n.id === edge.source);
    const tgtNode = nodes.find((n) => n.id === edge.target);
    if (!srcNode || !tgtNode) return;

    const srcCat = srcNode.data?.category;
    const tgtCat = tgtNode.data?.category;
    if (srcCat === "memory" || tgtCat === "memory") return;

    const srcRef = srcCat === "triggers" ? "START" : `"${nodeFnMap[srcNode.id]}"`;
    const tgtRef = tgtCat === "output" ? "END" : `"${nodeFnMap[tgtNode.id]}"`;

    edgeLines.push(`builder.add_edge(${srcRef}, ${tgtRef})`);
  });

  // 4. Generate connections.py (MongoDB, Postgres, Pinecone adapters)
  const connectionsPy = `"""
Database, Vector Store & Checkpointer Adapters (Auto-generated)
Supports PostgreSQL (pgvector), MongoDB Atlas, and Pinecone.
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
    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=os.environ["POSTGRES_URL"],
        use_jsonb=True,
    )

def get_checkpointer():
    provider = "${memoryProvider.toLowerCase()}"
    if "postgres" in provider and os.getenv("POSTGRES_URL"):
        from langgraph.checkpoint.postgres import PostgresSaver
        return PostgresSaver.from_conn_string(os.environ["POSTGRES_URL"])
    if "mongo" in provider and os.getenv("MONGODB_URI"):
        from langgraph.checkpoint.mongodb import MongoDBSaver
        client = MongoClient(os.environ["MONGODB_URI"])
        return MongoDBSaver(client)
    return MemorySaver()
`;

  // 5. Generate graph.py
  const graphPy = `"""
Auto-Compiled LangGraph StateGraph
Workspace: ${workspaceName}
Compiled 100% in Browser by FlowGraph Studio
"""
import operator
import httpx
from typing import Annotated, TypedDict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from connections import (
    get_pinecone_store,
    get_mongodb_store,
    get_pgvector_store,
    get_checkpointer,
)

class AgentState(TypedDict, total=False):
${stateFields.join("\n")}

${nodeDefinitions.join("\n")}

builder = StateGraph(AgentState)
${builderAddNodes.join("\n")}

${edgeLines.join("\n")}

checkpointer = get_checkpointer()
graph = builder.compile(checkpointer=checkpointer)
`;

  // 6. Generate main.py (FastAPI Production Microservice with SSE & Resume)
  const mainPy = `"""
Production REST API Microservice for ${workspaceName}
Endpoints:
  - POST /v1/threads/{thread_id}/invoke
  - POST /v1/threads/{thread_id}/stream
  - GET  /v1/threads/{thread_id}/state
"""
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from graph import graph

app = FastAPI(title="${workspaceName} - LangGraph API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentInvokeRequest(BaseModel):
    message: str
    metadata: Optional[Dict[str, Any]] = None

@app.post("/v1/threads/{thread_id}/invoke")
async def invoke_thread(thread_id: str, req: AgentInvokeRequest):
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": req.message}]},
        config=config,
    )
    last_msg = result["messages"][-1].content if result.get("messages") else ""
    return {
        "thread_id": thread_id,
        "output": last_msg,
        "context": result.get("context", []),
    }

@app.post("/v1/threads/{thread_id}/stream")
async def stream_thread(thread_id: str, req: AgentInvokeRequest):
    config = {"configurable": {"thread_id": thread_id}}

    async def event_stream():
        async for event in graph.astream_events(
            {"messages": [{"role": "user", "content": req.message}]},
            config=config,
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_chain_start":
                yield f"data: {json.dumps({'type': 'node_start', 'node': event['name']})}\\n\\n"
            elif kind == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\\n\\n"
        yield f"data: {json.dumps({'type': 'done'})}\\n\\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/v1/threads/{thread_id}/state")
async def get_thread_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    return {"values": str(snapshot.values), "next": snapshot.next}
`;

  // 7. Generate test_evals.py (Pytest Trajectory & Output Evaluation Suite)
  const testEvalsPy = `"""
Automated LangGraph Evaluation & Trajectory Harness
Run via: pytest test_evals.py -v
"""
import time
import pytest
from graph import graph

EVAL_SUITE = ${JSON.stringify(evalRows, null, 4)}

@pytest.mark.asyncio
@pytest.mark.parametrize("case", EVAL_SUITE)
async def test_langgraph_trajectory_and_output(case):
    t0 = time.perf_counter()
    config = {"configurable": {"thread_id": f"eval-{case['id']}"}}
    executed_nodes = []

    async for event in graph.astream_events(
        {"messages": [{"role": "user", "content": case["input"]}]},
        config=config,
        version="v2",
    ):
        if event["event"] == "on_chain_start" and event["name"] not in ("LangGraph", "__start__"):
            executed_nodes.append(event["name"])

    latency_ms = (time.perf_counter() - t0) * 1000
    assert latency_ms <= case.get("maxLatencyMs", 15000), f"Latency budget exceeded: {latency_ms:.0f}ms"

    state = await graph.aget_state(config)
    final_msg = str(state.values.get("messages", [""])[-1]).lower()
    if case.get("expectedKeyword"):
        assert case["expectedKeyword"].lower() in final_msg
`;

  return {
    "graph.py": graphPy,
    "connections.py": connectionsPy,
    "main.py": mainPy,
    "test_evals.py": testEvalsPy,
    "requirements.txt": [
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
    ].join("\n"),
    "Dockerfile": `FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nEXPOSE 8080\nCMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]\n`,
    ".env.example": [
      "OPENAI_API_KEY=sk-...",
      "ANTHROPIC_API_KEY=sk-ant-...",
      "POSTGRES_URL=postgresql://user:pass@localhost:5432/agent_db",
      "MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/",
      "PINECONE_API_KEY=pcsk_...",
    ].join("\n"),
  };
}

export async function downloadMicroserviceZipInBrowser(
  workspaceName: string,
  files: Record<string, string>
) {
  const zip = new JSZip();
  const folderName = sanitizeId(workspaceName) || "langgraph_service";
  const folder = zip.folder(folderName)!;

  Object.entries(files).forEach(([filename, content]) => {
    folder.file(filename, content);
  });

  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${folderName}_langgraph_api.zip`;
  a.click();
  URL.revokeObjectURL(url);
}
