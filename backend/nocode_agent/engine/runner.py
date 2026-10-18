"""
Full n8n-style Graph Execution Engine:
- Item-based data model: every node receives [{json: {...}}] and returns items per output port
- Topological traversal with concurrent fan-out and synchronized fan-in (Merge)
- Per-node retryOnFail, continueOnFail, and timeout
- Error branch routing (sourceHandle == 'error')
- Token streaming for LLM and Agent nodes
- SSE events with input_items and output_items
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator

from .models import make_item, ensure_item_list
from .nodes_logic import (
    execute_if_node,
    execute_switch_node,
    execute_merge_node,
    execute_loop_node,
    execute_wait_node,
    execute_set_node,
    execute_stop_and_error_node,
)
from .nodes_llm import execute_llm_node
from .nodes_tools import execute_tool_node, execute_knowledge_node, execute_memory_node
from .nodes_agent import execute_agent_node


async def execute_single_node(
    node: dict[str, Any],
    input_items: list[dict[str, Any]],
    connected_tools: list[dict[str, Any]] | None = None,
    credentials: dict[str, str] | None = None,
    node_context: dict[str, Any] | None = None,
    thread_id: str = "default",
    on_token: Any = None,
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Executes a single node in isolation with provided input items and context.
    """
    data = node.get("data", {})
    cat = data.get("category", "agents")
    cfg = data.get("config", {})
    label = data.get("label", node.get("id", "Node"))

    input_items = ensure_item_list(input_items)
    creds = credentials or {}
    ctx = node_context or {}
    tools = connected_tools or []

    # 1. Triggers
    if cat == "triggers":
        # Pass input items through or wrap initial message
        return {0: input_items}

    # 2. Logic nodes
    elif cat == "logic":
        logic_type = cfg.get("logicType") or label.lower()
        if "if" in logic_type:
            return await execute_if_node(cfg, input_items, ctx)
        elif "switch" in logic_type:
            return await execute_switch_node(cfg, input_items, ctx)
        elif "merge" in logic_type:
            return await execute_merge_node(cfg, [input_items])
        elif "loop" in logic_type:
            loop_state = ctx.setdefault("_loop_state", {})
            return await execute_loop_node(cfg, input_items, loop_state)
        elif "wait" in logic_type:
            return await execute_wait_node(cfg, input_items)
        elif "set" in logic_type or "edit" in logic_type:
            return await execute_set_node(cfg, input_items, ctx)
        elif "stop" in logic_type or "error" in logic_type:
            await execute_stop_and_error_node(cfg, input_items, ctx)
            return {0: input_items}
        else:
            # Default to IF condition evaluation
            return await execute_if_node(cfg, input_items, ctx)

    # 3. Models / LLM
    elif cat == "models":
        return await execute_llm_node(
            cfg=cfg,
            items=input_items,
            node_context=ctx,
            credentials=creds,
            on_token=on_token,
        )

    # 4. Autonomous Agents
    elif cat == "agents":
        return await execute_agent_node(
            cfg=cfg,
            items=input_items,
            connected_tools=tools,
            node_context=ctx,
            credentials=creds,
            on_token=on_token,
        )

    # 5. Tools
    elif cat == "tools":
        return await execute_tool_node(
            cfg=cfg,
            label=label,
            items=input_items,
            node_context=ctx,
        )

    # 6. Knowledge
    elif cat == "knowledge":
        return await execute_knowledge_node(
            cfg=cfg,
            items=input_items,
            node_context=ctx,
        )

    # 7. Memory
    elif cat == "memory":
        return await execute_memory_node(
            cfg=cfg,
            items=input_items,
            thread_id=thread_id,
        )

    # 8. Output / End
    elif cat == "output":
        return {0: input_items}

    # Default fallback
    return {0: input_items}


async def execute_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    user_input: str,
    credentials: dict[str, str],
    thread_id: str = "default",
    start_node_id: str | None = None,
    initial_items: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Executes a visual workflow graph in topological order with concurrent fan-out and fan-in.
    Yields SSE event dicts containing input_items, output_items, tokens, and trace info.
    """
    nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in nodes}
    t_start = time.perf_counter()

    # Discover connected tool nodes for each agent node
    connected_tools_by_agent: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        src = nodes_by_id.get(edge.get("source", ""))
        tgt = nodes_by_id.get(edge.get("target", ""))
        if src and tgt:
            if src.get("data", {}).get("category") == "agents" and tgt.get("data", {}).get("category") == "tools":
                connected_tools_by_agent.setdefault(src["id"], []).append(tgt)
            elif tgt.get("data", {}).get("category") == "agents" and src.get("data", {}).get("category") == "tools":
                connected_tools_by_agent.setdefault(tgt["id"], []).append(src)

    # Initial input items
    if initial_items:
        current_initial_items = ensure_item_list(initial_items)
    else:
        current_initial_items = [make_item({"message": user_input, "input": user_input})]

    yield {
        "event": "run_start",
        "thread_id": thread_id,
        "total_nodes": len(nodes),
    }

    # Event queue for thread-safe event streaming during concurrent execution
    event_queue: asyncio.Queue = asyncio.Queue()

    # Track execution state
    # node_outputs stores: node_id -> dict of port -> items, and node_label -> dict
    node_outputs: dict[str, Any] = {}
    visited_nodes: list[str] = []
    final_answer = ""

    # Find starting nodes
    if start_node_id and start_node_id in nodes_by_id:
        start_nodes = [nodes_by_id[start_node_id]]
    else:
        # Starting nodes are triggers, or nodes with in-degree 0
        target_ids = {e.get("target") for e in edges}
        triggers = [n for n in nodes if n.get("data", {}).get("category") == "triggers"]
        if triggers:
            start_nodes = triggers
        else:
            in_zero = [n for n in nodes if n["id"] not in target_ids]
            start_nodes = in_zero if in_zero else [nodes[0]] if nodes else []

    # Map of incoming inputs accumulated for each node: target_id -> list of incoming item lists
    accumulated_inputs: dict[str, list[list[dict[str, Any]]]] = {}
    # Count of expected incoming edges for each node (excluding error edges and self/loop edges)
    expected_in_degree: dict[str, int] = {}
    for edge in edges:
        tgt = edge.get("target")
        if tgt and edge.get("sourceHandle") != "error":
            expected_in_degree[tgt] = expected_in_degree.get(tgt, 0) + 1

    # Seed starting nodes with initial inputs
    for sn in start_nodes:
        accumulated_inputs[sn["id"]] = [current_initial_items]

    all_tasks: set[asyncio.Task] = set()

    def launch_task(coro):
        t = asyncio.create_task(coro)
        all_tasks.add(t)
        t.add_done_callback(all_tasks.discard)
        return t

    async def run_single_node_task(node_id: str, input_items: list[dict[str, Any]]):
        nonlocal final_answer
        node = nodes_by_id.get(node_id)
        if not node:
            return

        data = node.get("data", {})
        cat = data.get("category", "agents")
        cfg = data.get("config", {})
        label = data.get("label", node_id)

        visited_nodes.append(node_id)
        t_node = time.perf_counter()

        # Emit node_start with input_items
        await event_queue.put({
            "event": "node_start",
            "node_id": node_id,
            "label": label,
            "category": cat,
            "input_items": input_items,
        })

        async def token_emitter(delta: str):
            await event_queue.put({
                "event": "token",
                "node_id": node_id,
                "content": delta,
            })

        # Node settings: retryOnFail, continueOnFail, timeout
        max_tries = int(cfg.get("maxTries", 3)) if cfg.get("retryOnFail") else 1
        wait_between_tries = float(cfg.get("waitBetweenTries", 1.0))
        continue_on_fail = bool(cfg.get("continueOnFail", False))
        timeout_sec = float(cfg.get("timeout")) if cfg.get("timeout") else None

        ports_result: dict[int | str, list[dict[str, Any]]] = {}
        node_error: Exception | None = None

        for attempt in range(max_tries):
            try:
                exec_coro = execute_single_node(
                    node=node,
                    input_items=input_items,
                    connected_tools=connected_tools_by_agent.get(node_id, []),
                    credentials=credentials,
                    node_context=node_outputs,
                    thread_id=thread_id,
                    on_token=token_emitter,
                )

                if timeout_sec and timeout_sec > 0:
                    ports_result = await asyncio.wait_for(exec_coro, timeout=timeout_sec)
                else:
                    ports_result = await exec_coro

                node_error = None
                break
            except Exception as exc:
                node_error = exc
                if attempt < max_tries - 1:
                    await asyncio.sleep(wait_between_tries)

        latency_ms = int((time.perf_counter() - t_node) * 1000)

        # Handle failure
        if node_error is not None:
            err_msg = str(node_error)
            await event_queue.put({
                "event": "error",
                "node_id": node_id,
                "label": label,
                "error": err_msg,
            })

            # Check if there is an outgoing error branch
            error_edges = [
                e for e in edges
                if e.get("source") == node_id and (e.get("sourceHandle") == "error" or e.get("handle") == "error")
            ]
            if error_edges:
                error_item = [make_item({"error": err_msg, "failed_node": node_id, "failed_label": label})]
                for e_edge in error_edges:
                    tgt_id = e_edge.get("target")
                    if tgt_id:
                        accumulated_inputs.setdefault(tgt_id, []).append(error_item)
                        # Schedule error branch target immediately
                        asyncio.create_task(schedule_node_if_ready(tgt_id))
            elif not continue_on_fail:
                # Halt execution on unhandled error
                return

            if continue_on_fail:
                ports_result = {0: [make_item({"error": err_msg, "failed": True})]}

        # Record output for context
        main_output = ports_result.get(0) or ports_result.get("0") or [make_item({})]
        node_outputs[node_id] = main_output
        node_outputs[label] = main_output

        # Check for final answer in output
        if main_output and isinstance(main_output[0], dict):
            j = main_output[0].get("json", {})
            if "response" in j:
                final_answer = j["response"]
            elif "output" in j:
                final_answer = str(j["output"])

        # Emit node_end with output_items
        await event_queue.put({
            "event": "node_end",
            "node_id": node_id,
            "label": label,
            "category": cat,
            "output_items": main_output,
            "ports": {str(k): v for k, v in ports_result.items()},
            "latencyMs": latency_ms,
        })

        # Route to downstream nodes
        outgoing = [e for e in edges if e.get("source") == node_id]
        for edge in outgoing:
            handle = edge.get("sourceHandle")
            target_id = edge.get("target")
            if not target_id or handle == "error":
                continue

            # Determine which items route through this edge
            port_key: int | str = 0
            if handle is not None:
                if str(handle).isdigit():
                    port_key = int(handle)
                elif handle in ("true", "0"):
                    port_key = 0
                elif handle in ("false", "1"):
                    port_key = 1
                elif handle in ("loop",):
                    port_key = 0
                elif handle in ("done",):
                    port_key = 1
                else:
                    port_key = handle

            items_to_send = ports_result.get(port_key)
            if items_to_send is None:
                items_to_send = ports_result.get(str(port_key), [])

            if items_to_send:
                accumulated_inputs.setdefault(target_id, []).append(items_to_send)
                launch_task(schedule_node_if_ready(target_id))

    async def schedule_node_if_ready(target_node_id: str):
        if target_node_id not in nodes_by_id:
            return

        expected = expected_in_degree.get(target_node_id, 1)
        received = accumulated_inputs.get(target_node_id, [])

        target_node = nodes_by_id[target_node_id]
        cat = target_node.get("data", {}).get("category", "")
        is_merge = (cat == "logic" and "merge" in target_node.get("data", {}).get("label", "").lower())

        if is_merge and len(received) < expected:
            return

        if is_merge:
            merged_items = []
            for grp in received:
                merged_items.extend(grp)
            input_items = merged_items or [make_item({})]
        else:
            input_items = received[-1] if received else [make_item({})]

        await run_single_node_task(target_node_id, input_items)

    # Launch initial nodes
    for sn in start_nodes:
        launch_task(run_single_node_task(sn["id"], current_initial_items))

    # Background coordinator that waits for all tasks to complete and then closes event queue
    async def coordinator():
        while all_tasks:
            current_snapshot = list(all_tasks)
            await asyncio.gather(*current_snapshot, return_exceptions=True)
        await event_queue.put(None)  # Sentinel to signal completion

    asyncio.create_task(coordinator())

    # Stream SSE events as they occur
    while True:
        evt = await event_queue.get()
        if evt is None:
            break
        yield evt

    total_ms = int((time.perf_counter() - t_start) * 1000)

    # Final answer fallback if not set
    if not final_answer and visited_nodes:
        last_id = visited_nodes[-1]
        last_out = node_outputs.get(last_id, [{}])
        if last_out and isinstance(last_out[0], dict):
            final_answer = str(last_out[0].get("json", ""))

    yield {
        "event": "done",
        "finalAnswer": final_answer,
        "visitedNodes": visited_nodes,
        "totalMs": total_ms,
    }
