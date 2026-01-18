"""Instagram Graph API client"""

import time
from typing import Dict, Any, Optional, List
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..utils.logger import get_logger
from ..utils.exceptions import (
    InstagramAPIError,
    RateLimitError,
    ProxyError,
)
from .rate_limiter import RateLimiter

logger = get_logger(__name__)


class InstagramClient:
    """Client for Instagram Graph API with rate limiting and error handling"""
    
    def __init__(
        self,
        access_token: str,
        api_base_url: str = "https://graph.instagram.com",
        api_version: str = "v18.0",
        rate_limiter: Optional[RateLimiter] = None,
        proxy_url: Optional[str] = None,
        connection_timeout: int = 10,
    ):
        self.access_token = access_token
        self.api_base_url = api_base_url
        self.api_version = api_version
        self.rate_limiter = rate_limiter or RateLimiter()
        self.proxy_url = proxy_url
        self.connection_timeout = connection_timeout
        
        self.base_url = f"{api_base_url}/{api_version}"
        self.session = requests.Session()
        
        # Configure proxy if provided
        if proxy_url:
            self.session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Instagram API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Request body data
            files: Files to upload
            
        Returns:
            API response as dictionary
            
        Raises:
            InstagramAPIError: If API returns an error
            RateLimitError: If rate limit is exceeded
            ProxyError: If proxy connection fails
        """
        # Acquire rate limit permission
        self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Add access token to params
        if params is None:
            params = {}
        params["access_token"] = self.access_token
        
        try:
            logger.debug(
                "Making Instagram API request",
                method=method,
                endpoint=endpoint,
                has_proxy=bool(self.proxy_url),
            )
            
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data if not files else None,
                data=data if files else None,
                files=files,
                timeout=self.connection_timeout,
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    "Rate limit exceeded",
                    retry_after=retry_after,
                )
            
            result = response.json()
            
            # Handle HTTP errors and check for API errors in response
            if response.status_code >= 400:
                # Check for API error in response body
                if "error" in result:
                    error = result["error"]
                    error_code = error.get("code")
                    error_subcode = error.get("error_subcode")
                    error_message = error.get("message", "Unknown error")
                    error_type = error.get("type", "Unknown")
                    
                    if error_code == 4:  # Rate limit error code
                        retry_after = error.get("error_data", {}).get("retry_after", 60)
                        raise RateLimitError(error_message, retry_after=retry_after)
                    
                    raise InstagramAPIError(
                        f"{error_type}: {error_message} (code: {error_code})",
                        error_code=error_code,
                        error_subcode=error_subcode,
                    )
                else:
                    # No error in response body, raise HTTP error
                    response.raise_for_status()
            
            # Check for API errors in response (even on 200 status)
            if "error" in result:
                error = result["error"]
                error_code = error.get("code")
                error_subcode = error.get("error_subcode")
                error_message = error.get("message", "Unknown error")
                
                if error_code == 4:  # Rate limit error code
                    retry_after = error.get("error_data", {}).get("retry_after", 60)
                    raise RateLimitError(error_message, retry_after=retry_after)
                
                raise InstagramAPIError(
                    error_message,
                    error_code=error_code,
                    error_subcode=error_subcode,
                )
            
            return result
        
        except requests.exceptions.ProxyError as e:
            raise ProxyError(f"Proxy connection failed: {str(e)}")
        except requests.exceptions.Timeout as e:
            raise InstagramAPIError(f"Request timeout: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise InstagramAPIError(f"Request failed: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def get_account_info(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get account information
        
        Args:
            account_id: Optional Instagram account ID to use instead of /me
        """
        if account_id:
            return self._make_request("GET", account_id, params={"fields": "id,username,account_type"})
        return self._make_request("GET", "me", params={"fields": "id,username,account_type"})
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def create_media_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        caption: str = "",
        location_id: Optional[str] = None,
        user_tags: Optional[list] = None,
    ) -> str:
        """
        Create a media container for posting
        
        Returns:
            Container ID for publishing
        """
        # Verify media URL is accessible before sending to Instagram
        media_url = image_url or video_url
        if media_url:
            self._verify_media_url(media_url)
        
        params = {"caption": caption}
        
        if image_url:
            params["image_url"] = image_url
            logger.info(
                "Creating image media container",
                image_url=image_url,
                url_length=len(image_url),
            )
        elif video_url:
            params["media_type"] = "VIDEO"
            params["video_url"] = video_url
            logger.info(
                "Creating video media container",
                video_url=video_url,
                url_length=len(video_url),
            )
        else:
            raise InstagramAPIError("Either image_url or video_url must be provided")
        
        if location_id:
            params["location_id"] = location_id
        
        if user_tags:
            params["user_tags"] = ",".join(user_tags)
        
        # Log the exact request being sent
        logger.debug(
            "Sending media container creation request to Instagram",
            endpoint="me/media",
            has_image_url=bool(image_url),
            has_video_url=bool(video_url),
            params_keys=list(params.keys()),
        )
        
        try:
            response = self._make_request("POST", "me/media", data=params)
            container_id = response.get("id")
            logger.info(
                "Media container created successfully",
                container_id=container_id,
                media_url=media_url,
            )
            return container_id
        except InstagramAPIError as e:
            # Add more context to the error
            logger.error(
                "Failed to create media container",
                error=str(e),
                error_code=getattr(e, 'error_code', None),
                error_subcode=getattr(e, 'error_subcode', None),
                media_url=media_url,
            )
            raise
    
    def _verify_media_url(self, url: str) -> bool:
        """
        Verify that a media URL is accessible and returns correct content type.
        This helps catch issues before sending to Instagram.
        
        Args:
            url: Media URL to verify
            
        Returns:
            True if URL is accessible
            
        Raises:
            InstagramAPIError: If URL is not accessible or returns wrong content type
        """
        try:
            # Use a simple HEAD request to check accessibility
            # Use a generic User-Agent that won't be blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/*,video/*,*/*",
            }
            
            logger.debug("Verifying media URL accessibility", url=url)
            
            response = self.session.head(
                url,
                headers=headers,
                timeout=10,
                allow_redirects=True,
            )
            
            # Check if we got a successful response
            if response.status_code != 200:
                raise InstagramAPIError(
                    f"Media URL returned status {response.status_code} instead of 200. "
                    f"URL may not be publicly accessible. URL: {url}",
                    error_code=9004,
                )
            
            # Verify Content-Type header
            content_type = response.headers.get("Content-Type", "").lower()
            is_image = any(ct in content_type for ct in ["image/", "image/jpeg", "image/png", "image/gif", "image/webp"])
            is_video = any(ct in content_type for ct in ["video/", "video/mp4", "video/quicktime"])
            
            if not (is_image or is_video):
                logger.warning(
                    "Media URL Content-Type may be incorrect",
                    url=url,
                    content_type=content_type,
                    expected="image/* or video/*",
                )
                # Don't fail here - Instagram might still accept it
                # But log the warning
            
            logger.debug(
                "Media URL verification successful",
                url=url,
                content_type=content_type,
                content_length=response.headers.get("Content-Length"),
            )
            
            return True
            
        except requests.exceptions.Timeout:
            raise InstagramAPIError(
                f"Media URL verification timeout. URL may not be accessible. URL: {url}",
                error_code=9004,
            )
        except requests.exceptions.RequestException as e:
            raise InstagramAPIError(
                f"Media URL is not accessible: {str(e)}. URL: {url}",
                error_code=9004,
            )
        except Exception as e:
            # If verification fails but we can't determine why, log and continue
            logger.warning(
                "Media URL verification failed, but continuing anyway",
                url=url,
                error=str(e),
            )
            return True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def publish_media(self, creation_id: str) -> Dict[str, Any]:
        """
        Publish a media container
        
        Args:
            creation_id: Container ID from create_media_container
            
        Returns:
            Published media information
        """
        return self._make_request(
            "POST",
            "me/media_publish",
            data={"creation_id": creation_id},
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def create_carousel_container(
        self,
        children: list,
        caption: str = "",
        location_id: Optional[str] = None,
    ) -> str:
        """
        Create a carousel media container
        
        Args:
            children: List of child media container IDs
            caption: Post caption
            location_id: Optional location ID
            
        Returns:
            Container ID for publishing
        """
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
        }
        
        if location_id:
            params["location_id"] = location_id
        
        response = self._make_request("POST", "me/media", data=params)
        return response["id"]
    
    def get_media_status(self, container_id: str) -> Dict[str, Any]:
        """Check the status of a media container"""
        return self._make_request("GET", f"{container_id}", params={"fields": "status_code"})
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def comment_on_media(self, media_id: str, message: str) -> Dict[str, Any]:
        """
        Comment on a media post
        
        Args:
            media_id: Instagram media ID to comment on
            message: Comment text
            
        Returns:
            Comment creation result
        """
        response = self._make_request(
            "POST",
            f"{media_id}/comments",
            data={"message": message},
        )
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def search_hashtag(self, hashtag: str, limit: int = 10) -> List[str]:
        """
        Search for recent media by hashtag (via Business Discovery API)
        
        Note: This requires additional permissions and may need to be
        implemented differently based on available API access.
        
        Args:
            hashtag: Hashtag to search (without #)
            limit: Maximum number of media IDs to return
            
        Returns:
            List of media IDs
        """
        # Using Business Discovery API via Facebook Graph API
        # This requires the account to have access to Business Discovery
        # For now, we'll attempt a direct hashtag search
        # Note: Instagram Graph API v18.0 may require different approach
        
        # Alternative: Get recent media from account's timeline
        # This is a fallback approach when hashtag search isn't available
        try:
            # Try to get recent media from the account
            # This helps find media for warming actions
            response = self._make_request(
                "GET",
                "me/media",
                params={
                    "fields": "id,caption",
                    "limit": limit,
                },
            )
            
            if "data" in response:
                return [item["id"] for item in response["data"]]
            
            return []
        except InstagramAPIError as e:
            logger.warning(
                "Could not fetch media for warming actions",
                error=str(e),
                hashtag=hashtag,
            )
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def get_recent_media(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent media from the account's media library
        
        Args:
            limit: Maximum number of media items to return
            
        Returns:
            List of media information dictionaries
        """
        response = self._make_request(
            "GET",
            "me/media",
            params={
                "fields": "id,caption,media_type,permalink,timestamp",
                "limit": limit,
            },
        )
        
        if "data" in response:
            return response["data"]
        
        return []