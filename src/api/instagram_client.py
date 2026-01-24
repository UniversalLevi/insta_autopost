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
        connection_timeout: int = 60,
        read_timeout: int = 120,
    ):
        self.access_token = access_token
        self.api_base_url = api_base_url
        self.api_version = api_version
        self.rate_limiter = rate_limiter or RateLimiter()
        self.proxy_url = proxy_url
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        # Use tuple timeout: (connect_timeout, read_timeout)
        self.timeout = (connection_timeout, read_timeout)
        
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
            logger.info(
                "Making Instagram API request",
                method=method,
                endpoint=endpoint,
                timeout=self.timeout,
                has_proxy=bool(self.proxy_url),
            )
            
            # Use tuple timeout for better control (connect, read)
            # Instagram API can be slow, especially for media container creation
            timeout_value = self.timeout
            
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data if not files else None,
                data=data if files else None,
                files=files,
                timeout=timeout_value,
            )
            
            logger.info(
                "Received response from Instagram API",
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
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
            logger.error("Proxy connection failed", error=str(e), endpoint=endpoint)
            raise ProxyError(f"Proxy connection failed: {str(e)}")
        except requests.exceptions.Timeout as e:
            logger.error(
                "Request timeout",
                error=str(e),
                endpoint=endpoint,
                timeout=self.timeout,
            )
            raise InstagramAPIError(
                f"Request timeout after {self.timeout} seconds. "
                f"This usually means Instagram's API is slow or the media URL is taking too long to process. "
                f"Try again or check your media URL. Error: {str(e)}"
            )
        except requests.exceptions.RequestException as e:
            logger.error("Request failed", error=str(e), endpoint=endpoint)
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
        logger.info(
            "Sending media container creation request to Instagram",
            endpoint="me/media",
            has_image_url=bool(image_url),
            has_video_url=bool(video_url),
            params_keys=list(params.keys()),
            timeout=self.timeout,
        )
        
        try:
            logger.info(
                "Calling Instagram API to create media container",
                endpoint="me/media",
                has_image=bool(image_url),
                has_video=bool(video_url),
            )
            response = self._make_request("POST", "me/media", data=params)
            
            logger.info(
                "Received response from Instagram API",
                has_id="id" in response,
                response_keys=list(response.keys()) if isinstance(response, dict) else None,
            )
            
            container_id = response.get("id")
            
            if not container_id:
                logger.error(
                    "Instagram API returned response without container ID",
                    response=response,
                )
                raise InstagramAPIError("Instagram API did not return a container ID")
            
            logger.info(
                "Media container created successfully",
                container_id=container_id,
                media_url=media_url,
            )
            return container_id
        except InstagramAPIError as e:
            # Add more context to the error
            error_code = getattr(e, 'error_code', None)
            error_subcode = getattr(e, 'error_subcode', None)
            
            logger.error(
                "Failed to create media container",
                error=str(e),
                error_code=error_code,
                error_subcode=error_subcode,
                media_url=media_url,
                error_type=type(e).__name__,
            )
            
            # If error 9004, provide more helpful error message
            if error_code == 9004:
                raise InstagramAPIError(
                    f"Instagram cannot access the media URL (error 9004). "
                    f"This usually means:\n"
                    f"1) Cloudflare's trycloudflare.com is blocking Instagram's bot\n"
                    f"2) The URL is returning HTML instead of the image\n"
                    f"3) The server is blocking Instagram's crawler\n\n"
                    f"Solution: Use a production static file host like AWS S3, Cloudinary, or Firebase Storage\n"
                    f"URL: {media_url}\n"
                    f"Original error: {str(e)}",
                    error_code=9004,
                    error_subcode=error_subcode,
                )
            raise
        except Exception as e:
            # Catch any other unexpected exceptions
            logger.error(
                "Unexpected error while creating media container",
                error=str(e),
                error_type=type(e).__name__,
                media_url=media_url,
                exc_info=True,
            )
            raise InstagramAPIError(
                f"Unexpected error creating media container: {str(e)}"
            ) from e
    
    def _verify_media_url(self, url: str) -> bool:
        """
        Verify that a media URL is accessible using Instagram's user agent.
        This simulates what Instagram's crawler will do and catches blocking issues early.
        
        Args:
            url: Media URL to verify
            
        Returns:
            True if URL is accessible
            
        Raises:
            InstagramAPIError: If URL is not accessible or returns wrong content type
        """
        try:
            # Use Instagram's actual user agent to test if Cloudflare will block it
            # This is the user agent Instagram's crawler uses
            headers = {
                "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                "Accept": "image/*,video/*,*/*",
            }
            
            logger.debug("Verifying media URL with Instagram's user agent", url=url)
            
            # Test with HEAD request first (Instagram does this)
            response = self.session.head(
                url,
                headers=headers,
                timeout=15,
                allow_redirects=True,
            )
            
            status_code = response.status_code
            content_type = response.headers.get("Content-Type", "").lower()
            
            logger.debug(
                "Media URL verification result",
                url=url,
                status_code=status_code,
                content_type=content_type,
            )
            
            # Check if we got a successful response
            if status_code != 200:
                raise InstagramAPIError(
                    f"Media URL returned status {status_code} instead of 200. "
                    f"This means Instagram's crawler cannot access the URL. "
                    f"Cloudflare's trycloudflare.com may be blocking Instagram's bot. "
                    f"URL: {url}",
                    error_code=9004,
                )
            
            # Verify Content-Type header
            is_image = any(ct in content_type for ct in ["image/jpeg", "image/png", "image/gif", "image/webp"])
            is_video = any(ct in content_type for ct in ["video/mp4", "video/quicktime"])
            
            # If Content-Type is text/html, the server is likely returning an error page
            if "text/html" in content_type:
                raise InstagramAPIError(
                    f"Media URL is returning HTML instead of an image/video. "
                    f"This usually means Cloudflare is showing a blocking page or the server returned an error. "
                    f"Content-Type: {content_type}. "
                    f"Instagram will reject this with error 9004. "
                    f"URL: {url}",
                    error_code=9004,
                )
            
            if not (is_image or is_video):
                logger.warning(
                    "Media URL Content-Type may not be recognized by Instagram",
                    url=url,
                    content_type=content_type,
                )
            
            # Also test with GET request to ensure we get actual binary data
            response_get = self.session.get(
                url,
                headers=headers,
                timeout=15,
                allow_redirects=True,
                stream=True,
            )
            
            if response_get.status_code != 200:
                raise InstagramAPIError(
                    f"Media URL GET request returned status {response_get.status_code}. "
                    f"Instagram cannot access media from this URL. "
                    f"URL: {url}",
                    error_code=9004,
                )
            
            # Read first few bytes to check if it's actually binary/image data
            chunk = next(response_get.iter_content(chunk_size=1024), b"")
            response_get.close()
            
            # Check if content looks like HTML (starts with <) or text
            if chunk.startswith(b"<") or chunk.startswith(b"<!DOCTYPE") or chunk.startswith(b"<html"):
                raise InstagramAPIError(
                    f"Media URL is returning HTML/text instead of binary image/video data. "
                    f"Cloudflare or the server is likely blocking Instagram's bot. "
                    f"Instagram will reject this with error 9004. "
                    f"URL: {url}",
                    error_code=9004,
                )
            
            logger.info(
                "Media URL verified successfully - Instagram should be able to access it",
                url=url,
                content_type=content_type,
                content_length=response.headers.get("Content-Length"),
            )
            
            return True
            
        except requests.exceptions.Timeout:
            raise InstagramAPIError(
                f"Media URL verification timeout. Instagram cannot access the URL. "
                f"This often happens with Cloudflare tunnels blocking bot traffic. "
                f"URL: {url}",
                error_code=9004,
            )
        except requests.exceptions.RequestException as e:
            raise InstagramAPIError(
                f"Media URL is not accessible to Instagram's crawler: {str(e)}. "
                f"Instagram will reject this with error 9004. "
                f"URL: {url}",
                error_code=9004,
            )
        except InstagramAPIError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # For other errors, log warning but don't fail (Instagram might still work)
            logger.warning(
                "Media URL verification had an issue, but continuing anyway",
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
            children: List of child media container IDs (must be 2-10)
            caption: Post caption
            location_id: Optional location ID
            
        Returns:
            Container ID for publishing
        """
        # Instagram requires 2-10 items for carousel
        if len(children) < 2:
            raise InstagramAPIError(
                f"Carousel posts require 2-10 items. You provided {len(children)}.",
                error_code=100,
            )
        if len(children) > 10:
            raise InstagramAPIError(
                f"Carousel posts can have maximum 10 items. You provided {len(children)}.",
                error_code=100,
            )
        
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
        }
        
        if location_id:
            params["location_id"] = location_id
        
        logger.info(
            "Creating carousel container",
            child_count=len(children),
            children=children[:3],  # Log first 3 IDs
        )
        
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((InstagramAPIError, RateLimitError)),
    )
    def send_direct_message(
        self,
        recipient_username: str,
        message: str,
        recipient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a direct message to a user via Instagram Graph API.
        
        Note: Instagram Graph API DM limitations:
        - Requires instagram_manage_messages permission
        - Can only send to users who have messaged you first (or via thread)
        - May require Business/Creator account with messaging enabled
        
        Args:
            recipient_username: Username of recipient (for identification)
            message: Message text to send
            recipient_id: Optional Instagram user ID (more reliable than username)
            
        Returns:
            Result dictionary with status and dm_id
        """
        try:
            # Instagram Graph API DM endpoint
            # First, we need to get or create a conversation thread
            # For now, we'll try the direct message endpoint
            
            # Method 1: Try sending via conversations API (if thread exists)
            # Method 2: Try sending via message_creatives API
            
            # Note: Instagram's DM API is complex and has restrictions
            # This is a simplified implementation that attempts to send DMs
            
            # Get account ID (IGSID)
            account_info = self.get_account_info()
            account_id = account_info.get("id")
            
            # Try to send via conversations API
            # This requires the user to have previously messaged you
            endpoint = f"{account_id}/messages"
            
            response = self._make_request(
                "POST",
                endpoint,
                data={
                    "recipient": {"username": recipient_username} if recipient_username else {"id": recipient_id},
                    "message": {"text": message},
                }
            )
            
            logger.info(
                "DM sent via Instagram Graph API",
                recipient_username=recipient_username,
                message_length=len(message),
            )
            
            return {
                "status": "success",
                "dm_id": response.get("id") or response.get("message_id"),
                "recipient": recipient_username,
            }
            
        except InstagramAPIError as e:
            error_code = getattr(e, 'error_code', None)
            
            # Common error codes for DM failures
            if error_code in [100, 200, 10]:
                # Permissions or business messaging not enabled
                logger.warning(
                    "DM failed - may require messaging permissions or user to message first",
                    recipient_username=recipient_username,
                    error_code=error_code,
                    error=str(e),
                )
            
            return {
                "status": "failed",
                "error": str(e),
                "error_code": error_code,
                "recipient": recipient_username,
            }