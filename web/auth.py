"""Simple password-based authentication for web dashboard"""

import os
import secrets
from typing import Optional, Dict
from datetime import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Get password from environment variable or use default
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "admin")
SESSION_COOKIE_NAME = "instaforge_session"

# Simple in-memory session store (use database in production)
sessions: Dict[str, datetime] = {}


class SessionAuth(HTTPBearer):
    """Session-based authentication"""
    
    async def __call__(self, request: Request) -> Optional[str]:
        """Check if request is authenticated"""
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        
        if not session_id or session_id not in sessions:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return session_id


def create_session() -> str:
    """Create a new session"""
    session_id = secrets.token_urlsafe(32)
    from datetime import datetime
    sessions[session_id] = datetime.utcnow()
    return session_id


def verify_session(session_id: Optional[str]) -> bool:
    """Verify if session is valid"""
    if not session_id:
        return False
    return session_id in sessions


def destroy_session(session_id: str):
    """Destroy a session"""
    if session_id in sessions:
        del sessions[session_id]


def check_password(password: str) -> bool:
    """Check if password is correct"""
    return password == WEB_PASSWORD


def require_auth(request: Request) -> Optional[str]:
    """Middleware to check authentication on routes"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    
    if not verify_session(session_id):
        return None
    
    return session_id
