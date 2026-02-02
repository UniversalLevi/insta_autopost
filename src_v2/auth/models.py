"""
V2 auth models.

These are logical models for the V2 authentication system. Persistence
uses JSON files under data/ to mirror the existing v1 pattern, keeping
dependencies minimal and behavior predictable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field


class UserV2(BaseModel):
    """V2 user record (email-based, SaaS-friendly)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    password_hash: str
    role: Literal["admin", "user"] = "user"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionV2(BaseModel):
    """V2 session record (opaque token)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    token: str
    expires_at: datetime

