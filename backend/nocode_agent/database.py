"""
Database layer for No-Code Agent (LangGraph visual builder).
SQLite persistence:
- data.db: App data (users, workflows with versioned graph JSON, credentials, execution metadata)
- checkpoints.db: LangGraph state checkpoints via SqliteSaver / AsyncSqliteSaver
No MongoDB, no Redis, no pinned_data, no thread_memory.
"""

import json
import uuid
import aiosqlite
import sqlite3
from typing import Any

from .config import DB_PATH, CHECKPOINTS_DB_PATH
from .graph_schema import GraphSchema

_db: aiosqlite.Connection | None = None


def new_id() -> str:
    """Generate a short unique identifier."""
    return uuid.uuid4().hex[:24]


_tables_ensured = False


async def get_db() -> aiosqlite.Connection:
    """Return (and lazily create) a shared async SQLite connection."""
    global _db, _tables_ensured
    if _db is None:
        _db = await aiosqlite.connect(str(DB_PATH))
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        if not _tables_ensured:
            _tables_ensured = True
            await _ensure_tables_internal(_db)
    return _db


async def close_db():
    """Gracefully close database connection on shutdown."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ── Checkpointers for LangGraph ──────────────────────────────────────────────

def get_sqlite_saver(db_path: str | None = None):
    """Return a synchronous LangGraph SqliteSaver connected to checkpoints.db."""
    from langgraph.checkpoint.sqlite import SqliteSaver
    target = db_path or str(CHECKPOINTS_DB_PATH)
    conn = sqlite3.connect(target, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


async def get_async_sqlite_saver(db_path: str | None = None):
    """Return an asynchronous LangGraph AsyncSqliteSaver connected to checkpoints.db."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    target = db_path or str(CHECKPOINTS_DB_PATH)
    return AsyncSqliteSaver.from_conn_string(target)


# ── Database Migration & Table Setup ─────────────────────────────────────────

async def ensure_tables():
    """Create tables and migrate any legacy workspace rows into versioned workflows."""
    db = await get_db()
    await _ensure_tables_internal(db)


async def _ensure_tables_internal(db: aiosqlite.Connection):
    # 1. Base tables
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            full_name       TEXT NOT NULL DEFAULT '',
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id              TEXT PRIMARY KEY,
            owner_id        TEXT NOT NULL,
            name            TEXT NOT NULL DEFAULT 'Untitled Workflow',
            graph           TEXT NOT NULL DEFAULT '{}',
            schema_version  TEXT NOT NULL DEFAULT '1.0',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS credentials (
            id              TEXT PRIMARY KEY,
            owner_id        TEXT NOT NULL UNIQUE,
            openai_key      TEXT NOT NULL DEFAULT '',
            anthropic_key   TEXT NOT NULL DEFAULT '',
            pinecone_key    TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS typed_credentials (
            id              TEXT PRIMARY KEY,
            owner_id        TEXT NOT NULL,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL,
            encrypted_value TEXT NOT NULL,
            metadata        TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS executions (
            id              TEXT PRIMARY KEY,
            workflow_id     TEXT NOT NULL,
            owner_id        TEXT NOT NULL,
            thread_id       TEXT NOT NULL DEFAULT 'default',
            mode            TEXT NOT NULL DEFAULT 'run',
            status          TEXT NOT NULL DEFAULT 'running',
            start_time      TEXT NOT NULL,
            end_time        TEXT,
            total_ms        INTEGER NOT NULL DEFAULT 0,
            error_message   TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS triggers (
            id              TEXT PRIMARY KEY,
            workflow_id     TEXT NOT NULL,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL,
            config          TEXT NOT NULL DEFAULT '{}',
            is_active       INTEGER NOT NULL DEFAULT 1,
            last_run        TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_workflows_owner
            ON workflows(owner_id);

        CREATE INDEX IF NOT EXISTS idx_typed_credentials_owner
            ON typed_credentials(owner_id);

        CREATE INDEX IF NOT EXISTS idx_executions_workflow
            ON executions(workflow_id);

        CREATE INDEX IF NOT EXISTS idx_executions_thread
            ON executions(thread_id);

        CREATE INDEX IF NOT EXISTS idx_triggers_workflow
            ON triggers(workflow_id);
    """)
    await db.commit()

    # 2. Check for legacy 'workspaces' table and migrate into 'workflows'
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workspaces'"
    )
    has_legacy_workspaces = await cursor.fetchone()

    if has_legacy_workspaces:
        col_cursor = await db.execute("PRAGMA table_info(workspaces)")
        columns = [row["name"] for row in await col_cursor.fetchall()]

        if "nodes" in columns:
            # Migrate old columns: nodes, edges, state_schema, eval_rows
            old_rows_cursor = await db.execute("SELECT * FROM workspaces")
            old_rows = await old_rows_cursor.fetchall()

            for r in old_rows:
                r_dict = dict(r)
                ws_id = r_dict.get("id")
                owner_id = r_dict.get("owner_id", "local")
                name = r_dict.get("name", "Untitled")

                # Parse old fields
                try:
                    nodes = json.loads(r_dict.get("nodes", "[]"))
                except Exception:
                    nodes = []
                try:
                    edges = json.loads(r_dict.get("edges", "[]"))
                except Exception:
                    edges = []
                try:
                    state_schema_raw = json.loads(r_dict.get("state_schema", "[]"))
                except Exception:
                    state_schema_raw = []

                # Convert to LangGraph GraphSchema
                state_fields = []
                for f in state_schema_raw:
                    state_fields.append({
                        "name": f.get("key", "messages"),
                        "type": f.get("type", "messages"),
                        "reducer": f.get("reducer", "add_messages"),
                        "default": f.get("default"),
                    })
                if not state_fields:
                    state_fields = [{"name": "messages", "type": "messages", "reducer": "add_messages", "default": []}]

                converted_nodes = []
                for n in nodes:
                    converted_nodes.append({
                        "id": n.get("id", new_id()),
                        "type": n.get("data", {}).get("category", "agent"),
                        "label": n.get("data", {}).get("label", n.get("id", "Node")),
                        "position": n.get("position", {"x": 0.0, "y": 0.0}),
                        "config": n.get("data", {}).get("config", {}),
                        "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
                    })

                converted_edges = []
                for e in edges:
                    handle = e.get("sourceHandle")
                    is_cond = handle in ("true", "false", "conditional") or bool(e.get("condition"))
                    converted_edges.append({
                        "id": e.get("id", new_id()),
                        "source": e.get("source", "START"),
                        "target": e.get("target", "END"),
                        "kind": "conditional" if is_cond else "normal",
                        "condition": {"handle": handle} if handle else None,
                    })

                graph_obj = {
                    "schema_version": "1.0",
                    "state": {
                        "fields": state_fields,
                        "input_fields": ["messages"],
                        "output_fields": ["messages"],
                    },
                    "nodes": converted_nodes,
                    "edges": converted_edges,
                    "subgraphs": {},
                    "settings": {
                        "checkpointer": "sqlite",
                        "recursion_limit": 25,
                        "interrupt_before": [],
                        "interrupt_after": [],
                        "store": {},
                        "config_fields": [],
                    },
                }

                # Insert into workflows if not exists
                await db.execute(
                    """
                    INSERT OR IGNORE INTO workflows (id, owner_id, name, graph, schema_version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, '1.0', ?, ?)
                    """,
                    (
                        ws_id,
                        owner_id,
                        name,
                        json.dumps(graph_obj),
                        r_dict.get("created_at", ""),
                        r_dict.get("updated_at", ""),
                    ),
                )

            # Drop old workspaces table and replace with view to workflows
            await db.execute("DROP TABLE workspaces")
            await db.execute("""
                CREATE VIEW IF NOT EXISTS workspaces AS
                SELECT id, owner_id, name, graph, schema_version, created_at, updated_at
                FROM workflows
            """)
            await db.commit()

    # 3. Migrate any legacy credentials into typed_credentials
    try:
        cur = await db.execute("SELECT COUNT(*) as cnt FROM typed_credentials")
        cnt_row = await cur.fetchone()
        if cnt_row and cnt_row["cnt"] == 0:
            leg_cur = await db.execute("SELECT * FROM credentials")
            for lr in await leg_cur.fetchall():
                lr_d = dict(lr)
                owner = lr_d.get("owner_id", "local")
                if lr_d.get("openai_key"):
                    await db.execute(
                        "INSERT INTO typed_credentials (id, owner_id, name, type, encrypted_value, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                        (new_id(), owner, "OpenAI API Key", "openai", lr_d["openai_key"], "{}"),
                    )
                if lr_d.get("anthropic_key"):
                    await db.execute(
                        "INSERT INTO typed_credentials (id, owner_id, name, type, encrypted_value, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                        (new_id(), owner, "Anthropic API Key", "anthropic", lr_d["anthropic_key"], "{}"),
                    )
            await db.commit()
    except Exception:
        pass


# ── Helper: row → dict ───────────────────────────────────────────────────────

def row_to_dict(row: aiosqlite.Row | dict) -> dict:
    """Convert a database row to a dict, decoding JSON graph column if present."""
    d = dict(row)
    if "graph" in d and isinstance(d["graph"], str):
        try:
            d["graph"] = json.loads(d["graph"])
        except Exception:
            pass
    return d
