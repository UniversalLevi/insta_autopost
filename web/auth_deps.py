"""
FastAPI dependencies for authentication and authorization.
"""

from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.models.user import User
from src.auth.user_auth import validate_session


security = HTTPBearer(auto_error=False)


def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from request (cookie or Authorization header)"""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    # Try cookie
    token = request.cookies.get("session_token")
    if token:
        return token
    
    return None


async def get_current_user(request: Request) -> User:
    """Dependency to get current authenticated user"""
    token = get_session_token(request)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = validate_session(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def require_role(role: str):
    """Dependency factory for role-based access control"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role} role",
            )
        return current_user
    
    return role_checker


# Pre-configured dependencies
require_admin = require_role("admin")
require_auth = get_current_user
