"""Post data models"""

from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class PostStatus(str, Enum):
    """Post status enumeration"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PostMedia(BaseModel):
    """Media file for a post"""
    media_type: str = Field(..., description="Type: image, video, reels, carousel")
    url: Optional[HttpUrl] = None
    local_path: Optional[str] = None
    caption: Optional[str] = None
    thumbnail_url: Optional[HttpUrl] = None
    
    # For carousel posts
    children: List["PostMedia"] = Field(default_factory=list)


class Post(BaseModel):
    """Instagram post model"""
    post_id: Optional[str] = None
    account_id: str
    media: PostMedia
    caption: str = ""
    location_id: Optional[str] = None
    user_tags: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    scheduled_time: Optional[datetime] = None
    status: PostStatus = PostStatus.PENDING
    instagram_media_id: Optional[str] = None
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
