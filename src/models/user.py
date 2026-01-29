"""User data models for authentication"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class User(BaseModel):
    """User model for authentication and authorization"""
    id: str
    username: str
    email: Optional[str] = None
    password_hash: str
    role: str = Field(default="user", pattern="^(admin|user)$")  # Only "admin" or "user"
    created_at: str  # ISO format timestamp
    is_active: bool = True
    created_by: Optional[str] = None  # User ID of admin who created this user (None for self-registered or default admin)
    
    class Config:
        frozen = True  # Immutable for thread safety
