"""Custom exceptions for Instagram management system"""

from typing import Optional


class InstaForgeError(Exception):
    """Base exception for InstaForge"""
    pass


class InstagramAPIError(InstaForgeError):
    """Error from Instagram Graph API"""
    
    def __init__(self, message: str, error_code: Optional[int] = None, error_subcode: Optional[int] = None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        super().__init__(message)


class RateLimitError(InstagramAPIError):
    """Rate limit exceeded error"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(message, error_code=4)


class AccountError(InstaForgeError):
    """Account-related error"""
    pass


class PostingError(InstaForgeError):
    """Posting-related error"""
    pass


class MediaURLUnavailableError(InstaForgeError):
    """Media URL is not accessible (404, HTML page, etc.). Do not retry."""
    pass


class ProxyError(InstaForgeError):
    """Proxy connection error"""
    pass


class ConfigError(InstaForgeError):
    """Configuration error"""
    pass
