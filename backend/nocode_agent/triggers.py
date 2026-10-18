"""
Triggers Layer for No-Code Agent.
Supports:
1. Webhooks: /api/v1/webhook/{workflow_id}/{path} with optional secret token and payload mapping.
2. Cron schedules via APScheduler (AsyncIOScheduler) with automatic restore on server startup.
3. Payload-to-graph input mapping and dynamic thread_id rules (uuid, static, payload field).
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import HTTPException

from .database import get_db, new_id, row_to_dict
from .subprocess_runner import run_langgraph_subprocess

logger = logging.getLogger("nocode_agent.triggers")

# Shared AsyncIOScheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("APScheduler background trigger service started.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler background trigger service stopped.")


# ── Thread ID Resolution Helper ───────────────────────────────────────────────

def resolve_thread_id(rule: str, payload: dict[str, Any], default_prefix: str = "trigger") -> str:
    """Resolve thread ID based on rule: 'uuid', 'static:<id>', 'field:<name>', or fallback."""
    if not rule or rule == "uuid":
        return f"{default_prefix}_{uuid.uuid4().hex[:12]}"
    if rule.startswith("static:"):
        return rule[7:].strip() or f"{default_prefix}_static"
    if rule.startswith("field:"):
        field_name = rule[6:].strip()
        val = payload.get(field_name)
        return str(val) if val is not None else f"{default_prefix}_{uuid.uuid4().hex[:8]}"
    return rule


# ── Payload Mapping Helper ───────────────────────────────────────────────────

def map_payload_to_input(mapping: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Map incoming payload into graph state input."""
    if not mapping:
        # Default: pass payload directly if dict, or wrap into messages
        if isinstance(payload, dict) and any(k in payload for k in ("messages", "input", "query", "text")):
            return payload
        return {"messages": [("user", json.dumps(payload, default=str))]}

    result: dict[str, Any] = {}
    for target_key, src_expr in mapping.items():
        if isinstance(src_expr, str) and src_expr.startswith("payload."):
            prop = src_expr[8:].strip()
            result[target_key] = payload.get(prop)
        elif isinstance(src_expr, str) and src_expr == "$payload":
            result[target_key] = payload
        else:
            result[target_key] = src_expr
    return result


# ── Cron Job Callback ─────────────────────────────────────────────────────────

async def _cron_trigger_job_handler(trigger_id: str, workflow_id: str):
    """Execute scheduled cron trigger and record execution."""
    logger.info("Executing cron trigger %s for workflow %s", trigger_id, workflow_id)
    try:
        db = await get_db()
        # 1. Fetch trigger
        t_cur = await db.execute("SELECT * FROM triggers WHERE id = ? AND is_active = 1", (trigger_id,))
        trigger_row = await t_cur.fetchone()
        if not trigger_row:
            return

        cfg = json.loads(trigger_row["config"] or "{}") if isinstance(trigger_row["config"], str) else {}
        input_data = cfg.get("input_data") or {"messages": [("user", "Scheduled cron trigger execution")]}
        thread_rule = cfg.get("thread_rule", "uuid")
        thread_id = resolve_thread_id(thread_rule, input_data, default_prefix=f"cron_{trigger_id[:8]}")

        # 2. Fetch workflow
        wf_cur = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        wf_row = await wf_cur.fetchone()
        if not wf_row:
            return
        wf_dict = row_to_dict(wf_row)
        graph_data = wf_dict.get("graph")
        if not graph_data or not graph_data.get("nodes"):
            return

        # 3. Create execution entry
        run_id = f"run_{new_id()[:16]}"
        now_str = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            INSERT INTO executions (id, workflow_id, owner_id, thread_id, mode, status, start_time, created_at)
            VALUES (?, ?, ?, ?, 'cron', 'running', ?, ?)
            """,
            (run_id, workflow_id, wf_dict.get("owner_id", "local"), thread_id, now_str, now_str),
        )
        await db.execute(
            "UPDATE triggers SET last_run = ?, updated_at = ? WHERE id = ?",
            (now_str, now_str, trigger_id),
        )
        await db.commit()

        # 4. Run workflow via subprocess in background
        async def _run_in_bg():
            try:
                async for _ in run_langgraph_subprocess(
                    graph_data=graph_data,
                    run_id=run_id,
                    thread_id=thread_id,
                    input_data=input_data,
                    stream_mode="updates",
                ):
                    pass
            except Exception as e:
                logger.error("Error in cron subprocess execution: %s", e)

        asyncio.create_task(_run_in_bg())

    except Exception as exc:
        logger.error("Failed to execute cron trigger %s: %s", trigger_id, exc)


# ── Register / Unregister Cron Jobs with APScheduler ──────────────────────────

def schedule_cron_job(trigger_row: dict[str, Any]):
    """Add a cron trigger to the APScheduler."""
    tid = trigger_row["id"]
    wfid = trigger_row["workflow_id"]
    cfg = json.loads(trigger_row["config"] or "{}") if isinstance(trigger_row["config"], str) else trigger_row.get("config", {})
    cron_expr = cfg.get("cron_expression", "*/5 * * * *")

    sched = get_scheduler()
    # Remove existing job if present
    if sched.get_job(tid):
        sched.remove_job(tid)

    if not trigger_row.get("is_active", 1):
        return

    try:
        cron_trigger = CronTrigger.from_crontab(cron_expr)
        sched.add_job(
            _cron_trigger_job_handler,
            trigger=cron_trigger,
            id=tid,
            name=f"cron_{tid}",
            args=[tid, wfid],
            replace_existing=True,
        )
        logger.info("Scheduled cron job '%s' with expression '%s'", tid, cron_expr)
    except Exception as exc:
        logger.error("Failed to parse cron expression '%s' for trigger %s: %s", cron_expr, tid, exc)


def unschedule_cron_job(trigger_id: str):
    """Remove a cron job from the scheduler."""
    sched = get_scheduler()
    if sched.get_job(trigger_id):
        sched.remove_job(trigger_id)


async def restore_active_triggers():
    """Called on server startup: load all active cron triggers from DB and register them."""
    start_scheduler()
    db = await get_db()
    cur = await db.execute("SELECT * FROM triggers WHERE is_active = 1 AND type = 'cron'")
    rows = await cur.fetchall()
    count = 0
    for r in rows:
        schedule_cron_job(dict(r))
        count += 1
    logger.info("Restored %d active cron triggers on startup.", count)


# ── Webhook Trigger Execution ─────────────────────────────────────────────────

async def handle_webhook_trigger(
    workflow_id: str,
    path: str,
    payload: dict[str, Any],
    token: Optional[str] = None,
) -> dict[str, Any]:
    """Execute active webhook trigger for given workflow_id and path."""
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM triggers WHERE workflow_id = ? AND type = 'webhook' AND is_active = 1",
        (workflow_id,),
    )
    rows = await cur.fetchall()

    matching_trigger = None
    for r in rows:
        r_dict = dict(r)
        cfg = json.loads(r_dict["config"] or "{}") if isinstance(r_dict["config"], str) else {}
        trigger_path = (cfg.get("path") or "").strip("/").lower()
        if trigger_path == path.strip("/").lower():
            matching_trigger = (r_dict, cfg)
            break

    if not matching_trigger:
        raise HTTPException(
            status_code=404,
            detail=f"No active webhook trigger registered for workflow '{workflow_id}' at path '{path}'.",
        )

    t_row, cfg = matching_trigger

    # 1. Validate secret token if configured
    secret_token = cfg.get("secret_token") or cfg.get("token")
    if secret_token and secret_token != token:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing webhook secret token.")

    # 2. Map payload to graph input
    mapping = cfg.get("payload_mapping") or {}
    input_data = map_payload_to_input(mapping, payload)

    # 3. Resolve thread ID
    thread_rule = cfg.get("thread_rule") or cfg.get("thread_id_rule", "uuid")
    thread_id = resolve_thread_id(thread_rule, payload, default_prefix="webhook")

    # 4. Fetch workflow graph
    wf_cur = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    wf_row = await wf_cur.fetchone()
    if not wf_row:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    wf_dict = row_to_dict(wf_row)
    graph_data = wf_dict.get("graph")
    if not graph_data or not graph_data.get("nodes"):
        raise HTTPException(status_code=400, detail="Workflow has no executable nodes.")

    # 5. Record execution
    run_id = f"run_{new_id()[:16]}"
    now_str = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO executions (id, workflow_id, owner_id, thread_id, mode, status, start_time, created_at)
        VALUES (?, ?, ?, ?, 'webhook', 'running', ?, ?)
        """,
        (run_id, workflow_id, wf_dict.get("owner_id", "local"), thread_id, now_str, now_str),
    )
    await db.execute(
        "UPDATE triggers SET last_run = ?, updated_at = ? WHERE id = ?",
        (now_str, now_str, t_row["id"]),
    )
    await db.commit()

    # 6. Spawn runner subprocess in background
    async def _run_webhook_bg():
        try:
            async for _ in run_langgraph_subprocess(
                graph_data=graph_data,
                run_id=run_id,
                thread_id=thread_id,
                input_data=input_data,
                stream_mode="updates",
            ):
                pass
        except Exception as e:
            logger.error("Error running webhook workflow %s: %s", run_id, e)

    asyncio.create_task(_run_webhook_bg())

    return {
        "status": "triggered",
        "run_id": run_id,
        "thread_id": thread_id,
        "workflow_id": workflow_id,
        "trigger_id": t_row["id"],
    }
