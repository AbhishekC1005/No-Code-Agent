"""
Database layer: async SQLite via aiosqlite.
All data lives in a single file (~/.nocode-agent/data.db by default).
No MongoDB, no Redis required.
"""

import os
import uuid
import json
import aiosqlite
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Data directory ───────────────────────────────────────────────────────────

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path.home() / ".nocode-agent")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "data.db"

_db: aiosqlite.Connection | None = None


def new_id() -> str:
    """Generate a short hex ID (like a Mongo ObjectId but UUID-based)."""
    return uuid.uuid4().hex


async def get_db() -> aiosqlite.Connection:
    """Return (and lazily create) a shared async SQLite connection."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(str(DB_PATH))
        _db.row_factory = aiosqlite.Row          # dict-like rows
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db():
    """Gracefully close the database on shutdown."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ── Table creation (idempotent) ──────────────────────────────────────────────

async def ensure_tables():
    """Create tables on startup if they don't already exist."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            full_name       TEXT NOT NULL DEFAULT '',
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id              TEXT PRIMARY KEY,
            owner_id        TEXT NOT NULL,
            name            TEXT NOT NULL DEFAULT 'Untitled',
            nodes           TEXT NOT NULL DEFAULT '[]',
            edges           TEXT NOT NULL DEFAULT '[]',
            state_schema    TEXT NOT NULL DEFAULT '[]',
            eval_rows       TEXT NOT NULL DEFAULT '[]',
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

        CREATE TABLE IF NOT EXISTS execution_logs (
            id              TEXT PRIMARY KEY,
            owner_id        TEXT NOT NULL,
            thread_id       TEXT NOT NULL DEFAULT 'default',
            input_message   TEXT NOT NULL DEFAULT '',
            final_answer    TEXT NOT NULL DEFAULT '',
            visited_nodes   TEXT NOT NULL DEFAULT '[]',
            total_ms        INTEGER NOT NULL DEFAULT 0,
            node_traces     TEXT NOT NULL DEFAULT '[]',
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_workspaces_owner
            ON workspaces(owner_id);
    """)
    await db.commit()


# ── Helper: row → dict with parsed JSON columns ─────────────────────────────

_JSON_FIELDS = {"nodes", "edges", "state_schema", "eval_rows",
                "visited_nodes", "node_traces"}


def row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert an aiosqlite.Row to a plain dict, JSON-decoding known fields."""
    d = dict(row)
    for key in _JSON_FIELDS:
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d
