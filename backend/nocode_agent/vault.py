"""
Fernet-based credential encryption at rest.
Key is derived from the auto-generated application secret (not a hard-coded default).
"""

import hashlib
import base64

from cryptography.fernet import Fernet

from .config import SECRET_KEY


def _get_fernet() -> Fernet:
    key_bytes = hashlib.sha256(SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_value(plain: str) -> str:
    """Encrypt a plaintext string (e.g. an API key) and return a Fernet token."""
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to plaintext. Returns '' on any failure."""
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return ""


def mask_key(raw: str) -> str:
    """Show first 4 and last 4 characters, mask the rest."""
    if not raw or len(raw) < 8:
        return "••••"
    return raw[:4] + "•" * (len(raw) - 8) + raw[-4:]
