"""
V2 auth "middleware" helpers.

We expose require_login() as a FastAPI dependency that:
- Reads the V2 session token from cookie or Authorization header
- Validates it via the V2 auth service
- Returns the authenticated user object
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from src_v2.auth.models import UserV2
from src_v2.auth import service as auth_service


def _extract_token(request: Request) -> Optional[str]:
    # Prefer cookie for browser flows
    token = request.cookies.get("v2_session_token")
    if token:
        return token
    # Fallback to Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )
    if not auth_header:
        return None
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


async def require_login(request: Request) -> UserV2:
    """
    Dependency for protected V2 routes.

    Raises 401 if the session is missing or invalid.
    """
    token = _extract_token(request)
    user = auth_service.validate_session(token or "")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def require_context(request: Request):
    """
    Dependency for V2 routes that need UserContext.
    Requires login and validates X-USER-ID and X-INSTAGRAM-ID (or query params)
    so the backend validates ownership. Returns UserContext.
    """
    user = await require_login(request)
    user_id_header = request.headers.get("X-USER-ID") or request.query_params.get("user_id")
    ig_id_header = request.headers.get("X-INSTAGRAM-ID") or request.query_params.get("instagram_id")
    if not user_id_header or not ig_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-USER-ID and X-INSTAGRAM-ID (or user_id, instagram_id query) required",
        )
    if user_id_header != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-USER-ID must match authenticated user",
        )
    from src_v2.core.account_resolver import resolve_context
    ctx = resolve_context(user_id_header, ig_id_header)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connected account not found or unavailable",
        )
    return ctx

