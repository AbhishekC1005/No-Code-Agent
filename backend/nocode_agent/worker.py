"""
Worker process for executing LangGraph projects in an isolated subprocess.
Invoked via: python -m nocode_agent.worker
Reads execution payload from stdin as JSON, imports graph.py,
executes graph.astream(...), and emits structured JSON lines to stdout.
"""

import asyncio
import json
import os
import sys
import traceback
from typing import Any

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def emit(event_obj: dict[str, Any]):
    """Write JSON line to stdout and flush immediately for parent process to read."""
    try:
        sys.stdout.write(json.dumps(event_obj, default=str) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


async def run_worker():
    # 1. Read input payload from file argument (preferred on Windows) or stdin
    try:
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                raw_input = f.read()
        else:
            raw_input = sys.stdin.readline()
            if not raw_input or not raw_input.strip():
                raw_input = sys.stdin.read()

        if not raw_input or not raw_input.strip():
            emit({"event": "error", "message": "Worker received empty payload."})
            emit({"event": "done", "status": "error"})
            return
        payload = json.loads(raw_input)
    except Exception as exc:
        emit({"event": "error", "message": f"Failed to parse worker input: {exc}"})
        emit({"event": "done", "status": "error"})
        return

    thread_id = payload.get("thread_id", "default")
    run_id = payload.get("run_id", "run_0")
    input_data = payload.get("input", {})
    stream_mode = payload.get("stream_mode", "updates")
    message = payload.get("message")
    resume_val = payload.get("resume")
    checkpoint_id = payload.get("checkpoint_id")

    if resume_val is not None:
        if resume_val == "__breakpoint__":
            input_data = None
        else:
            from langgraph.types import Command
            input_data = Command(resume=resume_val)
    elif message and "messages" not in input_data:
        input_data["messages"] = [("user", message)]

    emit({
        "event": "start",
        "run_id": run_id,
        "thread_id": thread_id,
        "stream_mode": stream_mode,
    })

    # 2. Dynamically import graph from cwd
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        import graph as graph_module
        builder = getattr(graph_module, "builder", None)
        compiled_graph = getattr(graph_module, "graph", None)
        if compiled_graph is None and builder is None:
            emit({"event": "error", "message": "Could not find 'graph' or 'builder' in graph.py"})
            emit({"event": "done", "status": "error"})
            return
    except Exception as exc:
        emit({
            "event": "error",
            "message": f"Failed to import graph.py: {exc}",
            "traceback": traceback.format_exc(),
        })
        emit({"event": "done", "status": "error"})
        return

    # 3. Execute graph with requested stream_mode
    config = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    db_path = os.environ.get("CHECKPOINTS_DB_PATH", "checkpoints.db")
    checkpointer_name = type(getattr(compiled_graph, "checkpointer", None)).__name__

    interrupt_before = getattr(graph_module, "interrupt_before", getattr(compiled_graph, "interrupt_before_nodes", []))
    interrupt_after = getattr(graph_module, "interrupt_after", getattr(compiled_graph, "interrupt_after_nodes", []))

    if checkpointer_name == "SqliteSaver" and builder is not None:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(db_path) as async_cp:
            await async_cp.setup()
            async_graph = builder.compile(
                checkpointer=async_cp,
                store=getattr(compiled_graph, "store", None),
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
            )
            await _execute_graph(async_graph, input_data, config, stream_mode, run_id)
    else:
        await _execute_graph(compiled_graph, input_data, config, stream_mode, run_id)


async def _execute_graph(compiled_graph, input_data, config, stream_mode, run_id):
    try:
        if stream_mode == "messages":
            async for chunk in compiled_graph.astream(input_data, config=config, stream_mode="messages"):
                if isinstance(chunk, tuple) and len(chunk) >= 2:
                    msg_chunk, meta = chunk[0], chunk[1]
                    node_name = meta.get("langgraph_node") or meta.get("node") or ""
                    token_content = getattr(msg_chunk, "content", str(msg_chunk))
                    emit({
                        "event": "token",
                        "node": node_name,
                        "token": token_content,
                    })
                else:
                    emit({"event": "token", "token": str(chunk)})

        elif stream_mode == "values":
            async for state_snapshot in compiled_graph.astream(input_data, config=config, stream_mode="values"):
                emit({
                    "event": "state_update",
                    "values": state_snapshot,
                })

        elif stream_mode == "debug":
            async for debug_event in compiled_graph.astream(input_data, config=config, stream_mode="debug"):
                emit({
                    "event": "debug",
                    "data": debug_event,
                })

        elif stream_mode == "custom":
            async for custom_chunk in compiled_graph.astream(input_data, config=config, stream_mode="custom"):
                emit({
                    "event": "custom",
                    "data": custom_chunk,
                })

        else:
            # Default: 'updates' mode
            async for update in compiled_graph.astream(input_data, config=config, stream_mode="updates"):
                if isinstance(update, dict):
                    if "__interrupt__" in update:
                        interrupt_list = []
                        for item in update["__interrupt__"]:
                            interrupt_list.append(getattr(item, "value", str(item)))
                        emit({
                            "event": "interrupt",
                            "interrupts": interrupt_list,
                            "run_id": run_id,
                        })
                        continue
                    for node_name, node_output in update.items():
                        # Signal node execution lifecycle
                        emit({
                            "event": "node_start",
                            "node": node_name,
                        })
                        emit({
                            "event": "node_end",
                            "node": node_name,
                            "output": node_output,
                        })
                        emit({
                            "event": "state_update",
                            "node": node_name,
                            "update": node_output,
                        })
                else:
                    emit({"event": "state_update", "update": update})

        # Fetch final state snapshot from checkpointer
        has_interrupt = False
        try:
            final_snapshot = await compiled_graph.aget_state(config)
            final_values = getattr(final_snapshot, "values", {})
            tasks = getattr(final_snapshot, "tasks", ())
            for t in tasks:
                if getattr(t, "interrupts", None):
                    has_interrupt = True
                    interrupt_list = [getattr(i, "value", str(i)) for i in t.interrupts]
                    emit({
                        "event": "interrupt",
                        "interrupts": interrupt_list,
                        "next": list(getattr(final_snapshot, "next", ())),
                        "checkpoint_id": final_snapshot.config.get("configurable", {}).get("checkpoint_id"),
                        "run_id": run_id,
                    })

            if not has_interrupt and getattr(final_snapshot, "next", ()):
                has_interrupt = True
                emit({
                    "event": "interrupt",
                    "interrupts": [{"type": "breakpoint", "node": list(final_snapshot.next)}],
                    "next": list(getattr(final_snapshot, "next", ())),
                    "checkpoint_id": final_snapshot.config.get("configurable", {}).get("checkpoint_id"),
                    "run_id": run_id,
                })

            emit({
                "event": "final_state",
                "values": final_values,
                "next": list(getattr(final_snapshot, "next", ())),
                "checkpoint_id": final_snapshot.config.get("configurable", {}).get("checkpoint_id"),
            })
        except Exception:
            pass

        if has_interrupt:
            emit({"event": "done", "status": "interrupted", "run_id": run_id})
        else:
            emit({"event": "done", "status": "success", "run_id": run_id})

    except Exception as exc:
        emit({
            "event": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })
        emit({"event": "done", "status": "error", "run_id": run_id, "error": str(exc)})


def main():
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
