"""Account data models"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    """Proxy configuration for an account"""
    enabled: bool = False
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    @property
    def proxy_url(self) -> Optional[str]:
        """Generate proxy URL if enabled"""
        if not self.enabled or not self.host or not self.port:
            return None
        
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


class WarmingConfig(BaseModel):
    """Warming up behavior configuration"""
    enabled: bool = True
    daily_actions: int = Field(default=10, ge=0, le=100)
    action_types: List[str] = Field(default_factory=lambda: ["like", "comment"])


class CommentToDMConfig(BaseModel):
    """
    Comment-to-DM automation configuration (LinkDM/autodms.in style).
    
    Features:
    - Tracks last processed comment ID per post
    - Flexible trigger keyword (AUTO or specific keyword)
    - One DM per user per post per day
    - Configurable safety limits
    """
    enabled: bool = False
    trigger_keyword: Optional[str] = "AUTO"  # "AUTO" for any comment, or specific keyword (case-insensitive)
    dm_message_template: Optional[str] = None  # Template with {username}, {link}, {post} placeholders
    link_to_send: Optional[str] = None  # Link to include in DM (PDF, checkout, etc.)
    daily_dm_limit: Optional[int] = 50  # Maximum DMs per day per account
    cooldown_seconds: Optional[int] = 5  # Minimum seconds between DMs
    
    class Config:
        frozen = True


class AIDMConfig(BaseModel):
    """
    AI DM Auto Reply configuration.
    
    Features:
    - Automated AI-powered replies to incoming DMs
    - Rate limiting (max 10 replies per user per day)
    - Natural, human-like responses using OpenAI
    """
    enabled: bool = False  # Enable/disable AI DM auto-reply
    
    class Config:
        frozen = True


class Account(BaseModel):
    """Instagram account model"""
    account_id: str
    username: str
    access_token: str
    basic_display_token: Optional[str] = None  # Secondary token for basic display features
    password: Optional[str] = None  # For browser automation login
    owner_id: Optional[str] = None  # User ID who owns this account (None = no owner, visible to all)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    warming: WarmingConfig = Field(default_factory=WarmingConfig)
    comment_to_dm: Optional[CommentToDMConfig] = None  # Comment-to-DM automation config
    ai_dm: Optional[AIDMConfig] = None  # AI DM auto-reply config
    # OAuth-connected account fields (optional; manual tokens omit these)
    expires_at: Optional[str] = None
    instagram_business_id: Optional[str] = None
    page_id: Optional[str] = None
    user_access_token: Optional[str] = None  # User token for fb_exchange_token refresh

    class Config:
        frozen = True  # Immutable for thread safety
