"""
User authentication service with password hashing and session management.
"""

import os
import secrets
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

try:
    import bcrypt
except ImportError:
    raise ImportError("bcrypt is required. Install with: pip install bcrypt")

from src.models.user import User
from src.utils.exceptions import ConfigError

# Lazy import to avoid circular dependency
def _get_user_store():
    from src.services.user_store import user_store
    return user_store


DATA_DIR = Path("data")
SESSIONS_FILE = DATA_DIR / "sessions.json"

# Session expiration: 24 hours
SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def create_session(user_id: str) -> str:
    """Create a new session and return the session token"""
    token = secrets.token_urlsafe(32)
    
    # Load existing sessions
    sessions = _load_sessions()
    
    # Create session data
    expires_at = (datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat()
    sessions[token] = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at,
    }
    
    # Save sessions
    _save_sessions(sessions)
    
    return token


def validate_session(token: str) -> Optional[User]:
    """Validate a session token and return the associated user"""
    if not token:
        return None
    
    sessions = _load_sessions()
    
    if token not in sessions:
        return None
    
    session_data = sessions[token]
    
    # Check expiration
    expires_at = datetime.fromisoformat(session_data["expires_at"])
    if datetime.utcnow() > expires_at:
        # Session expired, remove it
        del sessions[token]
        _save_sessions(sessions)
        return None
    
    # Get user (lazy import to avoid circular dependency)
    user_store = _get_user_store()
    user = user_store.find_by_id(session_data["user_id"])
    
    # Check if user is active
    if not user or not user.is_active:
        # User is inactive or doesn't exist, remove session
        if token in sessions:
            del sessions[token]
            _save_sessions(sessions)
        return None
    
    return user


def logout_session(token: str) -> None:
    """Invalidate a session"""
    sessions = _load_sessions()
    if token in sessions:
        del sessions[token]
        _save_sessions(sessions)


def cleanup_expired_sessions() -> None:
    """Remove expired sessions (call periodically)"""
    sessions = _load_sessions()
    now = datetime.utcnow()
    
    expired_tokens = []
    for token, session_data in sessions.items():
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if now > expires_at:
            expired_tokens.append(token)
    
    if expired_tokens:
        for token in expired_tokens:
            del sessions[token]
        _save_sessions(sessions)


def _load_sessions() -> Dict[str, Any]:
    """Load sessions from JSON file"""
    if not SESSIONS_FILE.exists():
        return {}
    
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_sessions(sessions: Dict[str, Any]) -> None:
    """Atomically save sessions to JSON file"""
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    
    dir_path = SESSIONS_FILE.parent
    with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False, encoding='utf-8') as tf:
        json.dump(sessions, tf, indent=2, ensure_ascii=False)
        temp_path = Path(tf.name)
    
    try:
        # Atomic move/replace
        shutil.move(str(temp_path), str(SESSIONS_FILE))
    except Exception as e:
        # Clean up temp file if move failed
        if temp_path.exists():
            temp_path.unlink()
        raise ConfigError(f"Failed to save sessions to {SESSIONS_FILE}: {str(e)}")
