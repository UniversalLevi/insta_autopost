"""
FastAPI routes for V2 authentication.

Prefix: /v2/auth

This router is intentionally isolated from the v1 web stack; it can be
mounted on a separate FastAPI app or alongside the existing one without
interfering with legacy behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from src_v2.auth import service as auth_service
from src_v2.auth.models import UserV2
from .auth_middleware import require_login


router = APIRouter(prefix="/v2/auth", tags=["v2-auth"])


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


def _user_to_public(user: UserV2) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,  # type: ignore[arg-type]
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


def _set_session_cookie(response: Response, token: str) -> None:
    """
    Attach the V2 session token as a secure cookie.

    Clients can also use the token in Authorization headers if preferred.
    """
    import os

    is_prod = (os.getenv("ENVIRONMENT") or "").strip().lower() == "production"
    response.set_cookie(
        key="v2_session_token",
        value=token,
        max_age=7 * 24 * 60 * 60,  # 7 days
        httponly=True,
        secure=is_prod,
        samesite="lax",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    email: EmailStr = Form(...),
    password: str = Form(...),
) -> Any:
    """
    Register a new V2 user.

    Request (form-encoded):
        email: user email (unique)
        password: raw password

    Response:
        {
          "token": "<session_token>",
          "user": { "id": "...", "email": "...", "role": "user", "created_at": "..." }
        }
    """
    try:
        user = auth_service.create_user(email=email, password=password, role="user")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    token = auth_service.create_session(user.id)
    public_user = _user_to_public(user)
    response = JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=AuthResponse(token=token, user=public_user).model_dump(),
    )
    _set_session_cookie(response, token)
    return response


@router.post("/login", response_model=AuthResponse)
async def login(
    email: EmailStr = Form(...),
    password: str = Form(...),
) -> Any:
    """
    Log in an existing V2 user.

    Request (form-encoded):
        email, password

    Response:
        Same shape as /register.
    """
    user = auth_service.authenticate_user(email=email, password=password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = auth_service.create_session(user.id)
    public_user = _user_to_public(user)
    response = JSONResponse(
        content=AuthResponse(token=token, user=public_user).model_dump()
    )
    _set_session_cookie(response, token)
    return response


@router.post("/logout")
async def logout(request: Request) -> Dict[str, str]:
    """
    Log out current V2 session.

    Reads token from cookie or Authorization header.
    """
    from .auth_middleware import _extract_token  # reuse same logic

    token = _extract_token(request)
    if token:
        auth_service.logout(token)
    response = JSONResponse({"status": "success"})
    response.delete_cookie("v2_session_token")
    return response


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserV2 = Depends(require_login)) -> UserPublic:
    """
    Return the current authenticated V2 user.

    Requires a valid V2 session.
    """
    return _user_to_public(current_user)


@router.get("/users", response_model=List[UserPublic])
async def list_users_v2(current_user: UserV2 = Depends(require_login)) -> List[UserPublic]:
    """
    List users in the V2 auth system.

    - Admins: see all users
    - Normal users: see only themselves
    """
    if current_user.role == "admin":
        users = auth_service.list_users()
        return [_user_to_public(u) for u in users]
    # Normal user: only themselves
    return [_user_to_public(current_user)]

