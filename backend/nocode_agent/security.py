"""
Security utilities: JWT creation / validation and bcrypt password hashing.

In local single-user mode (AUTH_ENABLED=false), all endpoints that use
``get_current_user_optional`` fall back to a built-in local admin profile.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import SECRET_KEY, ALGORITHM, EXPIRE_MINUTES, AUTH_ENABLED
from .database import get_db

# ── Password hashing ────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── FastAPI dependencies ────────────────────────────────────────────────────

bearer_scheme = HTTPBearer()
bearer_scheme_optional = HTTPBearer(auto_error=False)

_DEFAULT_LOCAL_USER: dict = {
    "id": "local",
    "full_name": "Local User",
    "email": "admin@localhost",
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Require a valid JWT and return the matching user row."""
    payload = decode_access_token(credentials.credentials)
    user_email: str | None = payload.get("sub")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    db = await get_db()
    cursor = await db.execute("SELECT * FROM users WHERE email = ?", (user_email,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(row)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme_optional),
) -> dict:
    """Return authenticated user if token is valid, else the default local user.

    When ``AUTH_ENABLED=false`` (the default for self-hosted), this always
    returns the built-in local admin profile so the UI works without login.
    """
    if not AUTH_ENABLED:
        return _DEFAULT_LOCAL_USER

    if credentials and credentials.credentials:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_email = payload.get("sub")
            if user_email:
                db = await get_db()
                cursor = await db.execute("SELECT * FROM users WHERE email = ?", (user_email,))
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        except Exception:
            pass

    return _DEFAULT_LOCAL_USER


# ── Secret Redaction for Logging & Safe Output ────────────────────────────────

import re

_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
    re.compile(r"gAAAAA[a-zA-Z0-9_\-=]{20,}", re.IGNORECASE),  # Fernet tokens
]


def redact_secrets(text: str) -> str:
    """Redact API keys, tokens, and encrypted values from strings before logging or streaming."""
    if not text:
        return text
    sanitized = str(text)
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized
