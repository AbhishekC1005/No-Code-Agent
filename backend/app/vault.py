"""
Server-side credential vault.

Encrypts API keys at rest using Fernet symmetric encryption
(key derived from JWT_SECRET). For self-hosted single-user
deployments — credentials are stored once in MongoDB and
read by the runner during graph execution.
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()


def _get_fernet() -> Fernet:
    """Derive a Fernet key from JWT_SECRET."""
    secret = os.getenv("JWT_SECRET", "default-change-me")
    # SHA-256 → 32 bytes → base64 = valid Fernet key
    raw = hashlib.sha256(secret.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string. Returns empty string for empty input."""
    if not plaintext or not plaintext.strip():
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a string. Returns empty string on failure."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return ""


def mask_key(key: str) -> str:
    """Show first 5 and last 3 chars: sk-pr...abc"""
    if not key or len(key) < 10:
        return "••••••••" if key else ""
    return key[:5] + "•••" + key[-3:]
