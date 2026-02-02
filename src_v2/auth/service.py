"""
V2 authentication service layer.

This module implements a minimal, isolated auth stack for V2:
- Email/password users with bcrypt hashes
- Opaque session tokens with 7‑day expiry
- JSON-backed persistence in data/users_v2.json and data/sessions_v2.json

It does NOT touch or depend on the legacy v1 user/session system.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

try:
    import bcrypt
except ImportError:  # pragma: no cover - configuration error, not logic
    raise ImportError("bcrypt is required for V2 auth. Install with: pip install bcrypt")

from pydantic import EmailStr

from .models import UserV2, SessionV2

# Data directory can be overridden in tests via V2_DATA_DIR
DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
USERS_FILE = DATA_DIR / "users_v2.json"
SESSIONS_FILE = DATA_DIR / "sessions_v2.json"

# Session expiration: fixed 7 days for V2
SESSION_EXPIRY_DAYS = 7


def _atomic_write(path: Path, payload: Dict) -> None:
    """Atomically write JSON to the target path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf, indent=2, ensure_ascii=False, default=str)
        temp_path = Path(tf.name)
    try:
        shutil.move(str(temp_path), str(path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _load_users() -> List[UserV2]:
    if not USERS_FILE.exists():
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    items = raw.get("users", [])
    return [UserV2(**item) for item in items]


def _save_users(users: List[UserV2]) -> None:
    payload = {"users": [u.model_dump(mode="json") for u in users]}
    _atomic_write(USERS_FILE, payload)


def _load_sessions() -> Dict[str, SessionV2]:
    if not SESSIONS_FILE.exists():
        return {}
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    items = raw.get("sessions", {})
    out: Dict[str, SessionV2] = {}
    for token, data in items.items():
        try:
            out[token] = SessionV2(**data)
        except Exception:
            continue
    return out


def _save_sessions(sessions: Dict[str, SessionV2]) -> None:
    payload = {
        "sessions": {token: s.model_dump(mode="json") for token, s in sessions.items()}
    }
    _atomic_write(SESSIONS_FILE, payload)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def get_user_by_email(email: EmailStr) -> Optional[UserV2]:
    users = _load_users()
    for u in users:
        if u.email.lower() == email.lower():
            return u
    return None


def get_user_by_id(user_id: str) -> Optional[UserV2]:
    users = _load_users()
    return next((u for u in users if u.id == user_id), None)


def create_user(email: EmailStr, password: str, role: str = "user") -> UserV2:
    """
    Create a new V2 user.

    - Email must be unique (case-insensitive).
    - Password is stored only as a bcrypt hash.
    """
    users = _load_users()
    if any(u.email.lower() == email.lower() for u in users):
        raise ValueError("Email is already registered")

    user = UserV2(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password(password),
        role="admin" if role == "admin" else "user",
        created_at=datetime.utcnow(),
    )
    users.append(user)
    _save_users(users)
    return user


def authenticate_user(email: EmailStr, password: str) -> Optional[UserV2]:
    """Return user if credentials are valid, else None."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(user_id: str) -> str:
    """Create a new session and return its opaque token."""
    sessions = _load_sessions()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS)
    session = SessionV2(
        id=str(uuid4()),
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )
    sessions[token] = session
    _save_sessions(sessions)
    return token


def validate_session(token: str) -> Optional[UserV2]:
    """Validate a session token and return the associated user, or None."""
    if not token:
        return None
    sessions = _load_sessions()
    session = sessions.get(token)
    if not session:
        return None
    if datetime.utcnow() > session.expires_at:
        # Expired: remove session
        del sessions[token]
        _save_sessions(sessions)
        return None
    user = get_user_by_id(session.user_id)
    if not user:
        # Stale session pointing to missing user
        del sessions[token]
        _save_sessions(sessions)
        return None
    return user


def logout(token: str) -> None:
    """Invalidate a session token (idempotent)."""
    if not token:
        return
    sessions = _load_sessions()
    if token in sessions:
        del sessions[token]
        _save_sessions(sessions)


def list_users() -> List[UserV2]:
    """Return all V2 users (for admin views)."""
    return _load_users()


def _ensure_seed_admin() -> None:
    """
    Seed first admin user, if no V2 users exist yet.

    Admin credentials (change in production):
        email:    admin@instaforge.com
        password: admin123
    """
    users = _load_users()
    if users:
        return
    # Only seed if completely empty
    admin_email = os.getenv("V2_ADMIN_EMAIL", "admin@instaforge.com")
    admin_password = os.getenv("V2_ADMIN_PASSWORD", "admin123")
    admin = UserV2(
        id=str(uuid4()),
        email=admin_email,
        password_hash=hash_password(admin_password),
        role="admin",
        created_at=datetime.utcnow(),
    )
    _save_users([admin])


# Seed admin on first import in a safe, idempotent way.
_ensure_seed_admin()

