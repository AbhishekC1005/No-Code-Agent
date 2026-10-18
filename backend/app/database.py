"""
Database connections: async MongoDB (motor) + Redis client.
All connections are lazy-initialized on first use.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ──────────────────────────────────────────────────────────────────

_mongo_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/nocode_agent")
        _mongo_client = AsyncIOMotorClient(uri)
    return _mongo_client


def get_database() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        client = get_mongo_client()
        # Extract DB name from URI or default
        _db = client.get_default_database(default="nocode_agent")
    return _db


# Convenience accessors for collections
def users_collection():
    return get_database()["users"]


def workspaces_collection():
    return get_database()["workspaces"]


def credentials_collection():
    return get_database()["credentials"]


def execution_logs_collection():
    return get_database()["execution_logs"]


# ── Redis ────────────────────────────────────────────────────────────────────

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis = aioredis.from_url(url, decode_responses=True)
    return _redis


# ── Startup indexes ─────────────────────────────────────────────────────────

async def ensure_indexes():
    """Create MongoDB indexes on startup (idempotent)."""
    await users_collection().create_index("email", unique=True)
    await workspaces_collection().create_index("owner_id")
    await workspaces_collection().create_index([("owner_id", 1), ("name", 1)])
