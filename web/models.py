"""API request/response models for web dashboard"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class CreatePostRequest(BaseModel):
    """Request model for creating a post"""
    media_type: str = Field(..., description="Type: image, video, carousel, reels")
    urls: List[str] = Field(..., description="List of media URLs")
    caption: str = ""
    hashtags: List[str] = Field(default_factory=list)
    account_id: str
    scheduled_time: Optional[datetime] = None


class PostResponse(BaseModel):
    """Response model for post information"""
    post_id: Optional[str] = None
    account_id: str
    media_type: str
    caption: str
    hashtags: List[str]
    status: str
    instagram_media_id: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    error_message: Optional[str] = None


class LogEntry(BaseModel):
    """Log entry model"""
    timestamp: str
    level: str
    event: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class ConfigAccountResponse(BaseModel):
    """Account configuration response"""
    account_id: str
    username: str
    warming_enabled: bool
    daily_actions: int
    action_types: List[str]


class ConfigSettingsResponse(BaseModel):
    """App settings response"""
    warming_schedule_time: str
    rate_limit_per_hour: int
    rate_limit_per_minute: int
    posting_max_retries: int
    posting_retry_delay: int


class StatusResponse(BaseModel):
    """System status response"""
    app_status: str
    accounts: List[Dict[str, Any]]
    warming_enabled: bool
    warming_schedule: str


class PublishedPostResponse(BaseModel):
    """Published post from Instagram API"""
    id: str
    media_type: Optional[str] = None
    caption: Optional[str] = None
    permalink: Optional[str] = None
    timestamp: Optional[str] = None
