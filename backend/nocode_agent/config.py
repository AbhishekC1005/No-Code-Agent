"""
Centralized configuration for No-Code Agent.
Auto-generates a persistent secret on first run. All settings via env vars.
"""

import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Data directory ───────────────────────────────────────────────────────────

def _resolve_data_dir() -> Path:
    env_dir = os.getenv("NOCODE_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    default_p = Path.home() / ".nocode-agent"
    try:
        default_p.mkdir(parents=True, exist_ok=True)
        return default_p
    except (PermissionError, OSError):
        local_p = Path.cwd() / ".nocode-agent"
        local_p.mkdir(parents=True, exist_ok=True)
        return local_p

DATA_DIR = _resolve_data_dir()

# ── Auto-generated secret (persisted across restarts) ────────────────────────

_SECRET_FILE = DATA_DIR / "secret.key"


def _load_or_create_secret() -> str:
    """Load existing secret or generate and persist a new one."""
    if _SECRET_FILE.exists():
        secret = _SECRET_FILE.read_text().strip()
        if secret:
            return secret
    secret = secrets.token_hex(32)  # 64 hex characters
    _SECRET_FILE.write_text(secret)
    return secret


SECRET_KEY: str = os.getenv("JWT_SECRET") or _load_or_create_secret()

# ── Auth settings ────────────────────────────────────────────────────────────

AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# ── Database ─────────────────────────────────────────────────────────────────

DB_PATH = DATA_DIR / "data.db"
CHECKPOINTS_DB_PATH = DATA_DIR / "checkpoints.db"

# ── Frontend dist directory ──────────────────────────────────────────────────
# Priority: 1) development source tree  2) packaged inside wheel

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent   # nocode_agent → backend → root
_FRONTEND_DIST = _PROJECT_ROOT / "frontend" / "dist"
_PACKAGED_STATIC = Path(__file__).resolve().parent / "static"

if _FRONTEND_DIST.is_dir():
    STATIC_DIR: Path | None = _FRONTEND_DIST
elif _PACKAGED_STATIC.is_dir():
    STATIC_DIR = _PACKAGED_STATIC
else:
    STATIC_DIR = None

# ── Server & Security Settings ───────────────────────────────────────────────

HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]
