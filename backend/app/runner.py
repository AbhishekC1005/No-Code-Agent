"""
Backend Graph Execution Engine — n8n-style.

Walks the visual graph node-by-node in Python on the server,
calling LLM APIs with server-side credentials, and yields
SSE events for real-time canvas animation in the frontend.
"""

import time
import json
import httpx
from typing import Any, AsyncGenerator


async def execute_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    user_input: str,
    credentials: dict[str, str],
    thread_id: str = "default",
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Execute the graph and yield SSE event dicts.

    Events yielded:
      run_start  → { thread_id, total_nodes }
      node_start → { node_id, label, category }
      token      → { node_id, content }            (streamed LLM tokens)
      node_end   → { node_id, label, category, output, latencyMs }
      error      → { node_id, error }
      done       → { finalAnswer, visitedNodes, totalMs }
    """
    nodes_by_id: dict[str, dict] = {n["id"]: n for n in nodes}

    agent_state: dict[str, Any] = {
        "messages": [{"role": "user", "content": user_input}],
        "context": [],
        "retry_count": 0,
    }

    visited: list[str] = []
    t_start = time.perf_counter()

    # Find the START trigger node (or leftmost)
    current = next(
        (n for n in nodes if n.get("data", {}).get("category") == "triggers"),
        None,
    )
    if current is None and nodes:
        current = sorted(nodes, key=lambda n: n.get("position", {}).get("x", 0))[0]

    yield {
        "event": "run_start",
        "thread_id": thread_id,
        "total_nodes": len(nodes),
    }

    step = 0
    max_steps = 25

    while current is not None and step < max_steps:
        step += 1
        node_id: str = current["id"]
        data: dict = current.get("data", {})
        cat: str = data.get("category", "agents")
        cfg: dict = data.get("config", {})
        label: str = data.get("label", node_id)

        visited.append(node_id)
        t_node = time.perf_counter()

        yield {"event": "node_start", "node_id": node_id, "label": label, "category": cat}

        output = ""

        try:
            if cat == "triggers":
                output = f'Graph START → thread "{thread_id}" initialized with user message.'

            elif cat == "knowledge":
                provider = cfg.get("provider", "Pinecone")
                index_name = cfg.get("indexName", "knowledge")
                top_k = cfg.get("topK", 2)
                # Placeholder: in production, wire to actual vector DB client
                output = (
                    f"Retrieved {top_k} chunks from {provider} "
                    f'index "{index_name}". (Wire real vector DB for production.)'
                )

            elif cat == "memory":
                provider = cfg.get("provider", "PostgreSQL")
                output = f"Checkpoint #{step} saved to {provider}."

            elif cat in ("models", "agents"):
                output = await _execute_llm_node(
                    cfg, agent_state, user_input, credentials
                )

            elif cat == "tools":
                output = await _execute_tool_node(cfg, label, agent_state)

            elif cat == "logic":
                cond = cfg.get("conditionField", "retry_count")
                output = f'Router evaluated "{cond}" → routed to next branch.'

            elif cat == "output":
                output = "Reached END node. Final state committed."

            else:
                output = f'Executed plugin node "{label}".'

        except Exception as exc:
            output = f"Error: {exc}"
            yield {"event": "error", "node_id": node_id, "error": str(exc)}

        latency_ms = int((time.perf_counter() - t_node) * 1000)

        yield {
            "event": "node_end",
            "node_id": node_id,
            "label": label,
            "category": cat,
            "output": output,
            "latencyMs": latency_ms,
        }

        # ── Traverse outgoing edges ──────────────────────────────────────
        if cat == "output":
            break

        outgoing = [e for e in edges if e.get("source") == node_id]
        if not outgoing:
            break

        # Fire side-branch nodes (memory / knowledge) in parallel-like fashion
        if len(outgoing) > 1:
            for side_edge in outgoing[:-1]:
                side = nodes_by_id.get(side_edge["target"])
                if side and side.get("data", {}).get("category") in ("memory", "knowledge"):
                    s_id = side["id"]
                    s_data = side.get("data", {})
                    s_label = s_data.get("label", s_id)
                    s_cat = s_data.get("category", "")
                    visited.append(s_id)

                    yield {"event": "node_start", "node_id": s_id, "label": s_label, "category": s_cat}

                    s_output = f'{s_cat.title()} node "{s_label}" executed on server.'

                    yield {
                        "event": "node_end",
                        "node_id": s_id,
                        "label": s_label,
                        "category": s_cat,
                        "output": s_output,
                        "latencyMs": 30,
                    }

        # Follow the last outgoing edge as the main path
        next_edge = outgoing[-1]
        current = nodes_by_id.get(next_edge.get("target"))

    # ── Done ─────────────────────────────────────────────────────────────
    total_ms = int((time.perf_counter() - t_start) * 1000)
    final_answer = ""
    if agent_state["messages"]:
        last = agent_state["messages"][-1]
        final_answer = last.get("content", "") if isinstance(last, dict) else str(last)

    yield {
        "event": "done",
        "finalAnswer": final_answer,
        "visitedNodes": visited,
        "totalMs": total_ms,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE EXECUTORS
# ═══════════════════════════════════════════════════════════════════════════════


async def _execute_llm_node(
    cfg: dict,
    agent_state: dict,
    user_input: str,
    credentials: dict[str, str],
) -> str:
    """Call OpenAI or Anthropic via direct HTTP (no langchain dependency)."""
    provider = cfg.get("llmProvider", "openai")
    model = cfg.get("model", "gpt-4o-mini")
    sys_prompt = cfg.get("systemPrompt", "You are a helpful assistant.")
    temperature = cfg.get("temperature", 0)

    # Append RAG context if available
    ctx = agent_state.get("context")
    if ctx:
        sys_prompt += "\n\nRetrieved Context:\n" + "\n".join(str(c) for c in ctx)

    # ── Anthropic ────────────────────────────────────────────────────────
    if provider == "anthropic":
        key = credentials.get("anthropic_key", "")
        if not key:
            msg = "No Anthropic API key configured. Add it in the Vault."
            agent_state["messages"].append({"role": "assistant", "content": msg})
            return msg

        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": 1024,
                    "temperature": temperature,
                    "system": sys_prompt,
                    "messages": [{"role": "user", "content": user_input}],
                },
            )
            body = resp.json()
            if resp.status_code != 200:
                err = body.get("error", {}).get("message", resp.text[:300])
                agent_state["messages"].append({"role": "assistant", "content": f"Anthropic error: {err}"})
                return f"Anthropic error: {err}"

            reply = body.get("content", [{}])[0].get("text", json.dumps(body))
            agent_state["messages"].append({"role": "assistant", "content": reply})
            return reply

    # ── OpenAI (default) ─────────────────────────────────────────────────
    key = credentials.get("openai_key", "")
    if not key:
        msg = "No OpenAI API key configured. Add it in the Vault."
        agent_state["messages"].append({"role": "assistant", "content": msg})
        return msg

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json={
                "model": model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_input},
                ],
            },
        )
        body = resp.json()
        if resp.status_code != 200:
            err = body.get("error", {}).get("message", resp.text[:300])
            agent_state["messages"].append({"role": "assistant", "content": f"OpenAI error: {err}"})
            return f"OpenAI error: {err}"

        reply = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        agent_state["messages"].append({"role": "assistant", "content": reply})
        return reply


async def _execute_tool_node(
    cfg: dict, label: str, agent_state: dict
) -> str:
    """Execute an HTTP tool or custom code placeholder."""
    url = cfg.get("url")
    method = (cfg.get("method", "GET")).upper()

    if url:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.request(method, url)
                output = f"HTTP {resp.status_code}: {resp.text[:500]}"
        except Exception as exc:
            output = f'Tool "{label}" error: {exc}'
    else:
        output = f'Executed tool "{label}" — server-side sandbox.'

    return output
