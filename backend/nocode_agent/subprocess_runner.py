"""
Subprocess runner for executing generated LangGraph projects in worker subprocesses.
Streams JSON lines from worker stdout as SSE events to clients.
Applies execution limits, isolated credentials, cancellation, and thread state tracking.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, AsyncGenerator

from .codegen import generate_langgraph_project
from .config import CHECKPOINTS_DB_PATH
from .database import get_db, new_id

# Global map of active execution processes: run_id -> subprocess.Popen
ACTIVE_RUNS: dict[str, subprocess.Popen] = {}


async def cancel_run(run_id: str) -> bool:
    """Terminate an active running subprocess by run_id."""
    proc = ACTIVE_RUNS.get(run_id)
    if not proc:
        return False
    try:
        proc.terminate()
        try:
            await asyncio.to_thread(proc.wait, timeout=2.0)
        except Exception:
            proc.kill()
        return True
    except Exception:
        return False


async def run_langgraph_subprocess(
    graph_data: dict[str, Any],
    workflow_id: str = "default",
    thread_id: str = "default",
    run_id: str | None = None,
    input_data: dict[str, Any] | None = None,
    message: str | None = None,
    resume: Any | None = None,
    checkpoint_id: str | None = None,
    stream_mode: str = "updates",
    credentials: dict[str, str] | None = None,
    timeout_seconds: float = 60.0,
    owner_id: str = "local",
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Writes generated LangGraph project into a temporary workspace, launches
    'python -m nocode_agent.worker', relays output events, and cleans up.
    """
    run_id = run_id or f"run_{new_id()}"
    start_time = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    # 1. Log run start to executions table
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO executions (id, workflow_id, owner_id, thread_id, mode, status, start_time)
            VALUES (?, ?, ?, ?, ?, 'running', ?)
            """,
            (run_id, workflow_id, owner_id, thread_id, stream_mode, start_time.isoformat()),
        )
        await db.commit()
    except Exception:
        pass

    # 2. Generate LangGraph project files
    codegen_res = generate_langgraph_project(graph_data)
    files = codegen_res["files"]

    # 3. Write files to temporary working directory
    with tempfile.TemporaryDirectory(prefix=f"langgraph_{run_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        for fname, content in files.items():
            (temp_path / fname).write_text(content, encoding="utf-8")

        # Prepare worker environment
        worker_env = os.environ.copy()
        worker_env["PYTHONUNBUFFERED"] = "1"
        worker_env["PYTHONIOENCODING"] = "utf-8"
        worker_env["PYTHONUTF8"] = "1"
        worker_env["CHECKPOINTS_DB_PATH"] = str(CHECKPOINTS_DB_PATH)
        worker_env["STORE_DB_PATH"] = str(CHECKPOINTS_DB_PATH.parent / "store.db")

        # Include workspace root and temp directory in PYTHONPATH
        root_dir = str(Path(__file__).resolve().parent.parent.parent)
        backend_dir = str(Path(__file__).resolve().parent.parent)
        existing_pp = worker_env.get("PYTHONPATH", "")
        worker_env["PYTHONPATH"] = os.pathsep.join(
            [str(temp_path), backend_dir, root_dir, existing_pp] if existing_pp else [str(temp_path), backend_dir, root_dir]
        )

        # Injected credentials for this run only
        if credentials:
            for k, v in credentials.items():
                if v:
                    k_lower = k.lower()
                    if "openai" in k_lower:
                        worker_env["OPENAI_API_KEY"] = v
                    elif "anthropic" in k_lower:
                        worker_env["ANTHROPIC_API_KEY"] = v
                    elif "pinecone" in k_lower:
                        worker_env["PINECONE_API_KEY"] = v
                    else:
                        worker_env[k.upper()] = v

        # Resolve credential_ids referenced by nodes from typed_credentials table
        referenced_cred_ids = set()
        for n in graph_data.get("nodes", []):
            cfg = n.get("config", {})
            cid = cfg.get("credential_id") or cfg.get("credentialId")
            if cid:
                referenced_cred_ids.add(str(cid))

        if referenced_cred_ids:
            try:
                import sqlite3
                from .vault import decrypt_value
                from .config import DB_PATH
                conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                placeholders = ",".join("?" for _ in referenced_cred_ids)
                cur.execute(f"SELECT * FROM typed_credentials WHERE id IN ({placeholders})", tuple(referenced_cred_ids))
                for row in cur.fetchall():
                    val = decrypt_value(row["encrypted_value"])
                    ctype = str(row["type"]).lower()
                    meta = json.loads(row["metadata"] or "{}") if isinstance(row["metadata"], str) else {}
                    if ctype == "openai":
                        worker_env["OPENAI_API_KEY"] = val
                    elif ctype == "anthropic":
                        worker_env["ANTHROPIC_API_KEY"] = val
                    elif ctype == "ollama":
                        worker_env["OLLAMA_BASE_URL"] = val or meta.get("base_url", "http://localhost:11434")
                    elif ctype == "bearer":
                        worker_env[f"CRED_{row['id'].upper()}"] = val
                        if "env_var" in meta:
                            worker_env[meta["env_var"]] = val
                    else:
                        env_key = meta.get("env_var", f"CRED_{row['id'].upper()}")
                        worker_env[env_key] = val
                conn.close()
            except Exception:
                pass

        # Worker input payload
        worker_payload = {
            "run_id": run_id,
            "thread_id": thread_id,
            "stream_mode": stream_mode,
            "input": input_data or {},
            "message": message,
            "resume": resume,
            "checkpoint_id": checkpoint_id,
        }
        payload_file = temp_path / "payload.json"
        payload_file.write_text(json.dumps(worker_payload), encoding="utf-8")

        # 4. Spawn subprocess with Popen
        proc = subprocess.Popen(
            [sys.executable, "-m", "nocode_agent.worker", str(payload_file)],
            cwd=str(temp_path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=worker_env,
        )

        ACTIVE_RUNS[run_id] = proc
        status = "success"
        error_msg = None

        try:
            # Stream stdout line by line
            while True:
                line = await asyncio.to_thread(proc.stdout.readline)
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    event_data = json.loads(line_str)
                except Exception:
                    event_data = {"event": "raw", "data": line_str}

                if event_data.get("event") == "error":
                    status = "failed"
                    error_msg = event_data.get("message") or event_data.get("error")

                yield event_data

            # Await process exit
            try:
                await asyncio.to_thread(proc.wait, timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                status = "timeout"
                error_msg = f"Run exceeded timeout limit of {timeout_seconds}s"
                yield {"event": "error", "message": error_msg}
                proc.terminate()
                try:
                    await asyncio.to_thread(proc.wait, timeout=2.0)
                except Exception:
                    proc.kill()

            if proc.returncode != 0:
                stderr_output = (await asyncio.to_thread(proc.stderr.read)).strip() if proc.stderr else ""
                if stderr_output and status != "failed":
                    status = "failed"
                    error_msg = stderr_output
                    yield {"event": "error", "message": stderr_output}

        except asyncio.CancelledError:
            status = "cancelled"
            error_msg = "Run cancelled by user request"
            yield {"event": "error", "message": error_msg}
            proc.terminate()
            try:
                await asyncio.to_thread(proc.wait, timeout=2.0)
            except Exception:
                proc.kill()
            raise

        finally:
            ACTIVE_RUNS.pop(run_id, None)
            total_ms = int((time.perf_counter() - t0) * 1000)
            end_time = datetime.now(timezone.utc)

            # Update executions record
            try:
                await db.execute(
                    """
                    UPDATE executions
                    SET status = ?, end_time = ?, total_ms = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (status, end_time.isoformat(), total_ms, error_msg, run_id),
                )
                await db.commit()
            except Exception:
                pass
