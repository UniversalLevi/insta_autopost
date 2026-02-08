"""Instagram Graph API client"""

import time
import os
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
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
    MediaURLUnavailableError,
)
from .rate_limiter import RateLimiter

logger = get_logger(__name__)


def _is_own_server_url(url: str) -> bool:
    """Check if URL points to the app's own server (from BASE_URL/APP_URL)."""
    try:
        base_url = os.getenv("BASE_URL") or os.getenv("APP_URL")
        if not base_url:
            return False
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)
        url_host = (parsed_url.netloc or "").lower().split(":")[0]
        base_host = (parsed_base.netloc or "").lower().split(":")[0]
        return bool(url_host and base_host and url_host == base_host)
    except Exception:
        return False


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
        image_upload_timeout: int = 90,
        video_upload_timeout: int = 180,
    ):
        self.access_token = access_token
        self.api_base_url = api_base_url
        self.api_version = api_version
        self.rate_limiter = rate_limiter or RateLimiter()
        self.proxy_url = proxy_url
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.image_upload_timeout = image_upload_timeout
        self.video_upload_timeout = video_upload_timeout
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
        timeout_override: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Instagram API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Request body data
            files: Files to upload
            timeout_override: Optional (connect, read) timeout for this request
            
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
        
        timeout_value = timeout_override if timeout_override is not None else self.timeout
        
        try:
            logger.info(
                "Making Instagram API request",
                method=method,
                endpoint=endpoint,
                timeout=timeout_value,
                has_proxy=bool(self.proxy_url),
            )
            logger.debug(
                "Sending request to Instagram",
                endpoint=endpoint,
                timeout=timeout_value,
            )
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
                    
                    msg = f"{error_type}: {error_message} (code: {error_code})"
                    if error_code == 200:
                        msg += (
                            " Instagram has restricted API access for this account. "
                            "Check Meta for Developers app status or re-authenticate the account."
                        )
                    raise InstagramAPIError(
                        msg,
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
                
                if error_code == 200:
                    error_message = (
                        f"{error_message} "
                        "Instagram has restricted API access for this account. "
                        "Check Meta for Developers app status, re-authenticate the account, or ensure the app is not in development mode if it should be live."
                    )
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
                timeout=timeout_value,
            )
            raise InstagramAPIError(
                f"Request timeout after {timeout_value} seconds. "
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
        media_type: Optional[str] = None,
    ) -> str:
        """
        Create a media container for posting
        
        Returns:
            Container ID for publishing
        """
        # Strip query parameters from URLs (Instagram doesn't need them, and they can cause issues)
        # Query params are only for browser cache busting
        def clean_url(url: Optional[str]) -> Optional[str]:
            if not url:
                return url
            # Remove query parameters and fragments
            return url.split("?")[0].split("#")[0]
        
        image_url = clean_url(image_url)
        video_url = clean_url(video_url)
        
        # Verify media URL is accessible before sending to Instagram
        # NOTE: For production domains, we're more lenient - Instagram will verify anyway
        media_url = image_url or video_url
        if media_url:
            # Skip verification for production domains (Instagram will verify)
            # Only verify for development URLs to catch obvious mistakes
            is_production = not any(dev in media_url.lower() for dev in [
                "localhost", "127.0.0.1", "trycloudflare.com", "ngrok", "127.0.0.1"
            ])
            
            # Verify URL for both dev and production: 404 or HTML response means the URL is bad.
            # Failing here avoids pointless retries and gives a clear error (e.g. "URL returned 404").
            self._verify_media_url(media_url)
        
        params = {"caption": caption}
        
        # Handle media_type parameter (for reels)
        if media_type:
            params["media_type"] = media_type.upper()
        
        if image_url:
            params["image_url"] = image_url
            logger.info(
                "Creating image media container",
                image_url=image_url,
                url_length=len(image_url),
            )
        elif video_url:
            # If media_type not specified, default to VIDEO
            if not media_type:
                params["media_type"] = "VIDEO"
            params["video_url"] = video_url
            logger.info(
                "Creating video media container",
                video_url=video_url,
                url_length=len(video_url),
                media_type=params.get("media_type", "VIDEO"),
            )
        else:
            raise InstagramAPIError("Either image_url or video_url must be provided")
        
        if location_id:
            params["location_id"] = location_id
        
        if user_tags:
            params["user_tags"] = ",".join(user_tags)
        
        media_timeout = (
            (self.connection_timeout, self.video_upload_timeout)
            if video_url
            else (self.connection_timeout, self.image_upload_timeout)
        )
        logger.info(
            "Sending media container creation request to Instagram",
            endpoint="me/media",
            has_image_url=bool(image_url),
            has_video_url=bool(video_url),
            params_keys=list(params.keys()),
            timeout=media_timeout,
        )
        
        try:
            logger.info(
                "Calling Instagram API to create media container",
                endpoint="me/media",
                has_image=bool(image_url),
                has_video=bool(video_url),
            )
            response = self._make_request("POST", "me/media", data=params, timeout_override=media_timeout)
            
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
            error_type = type(e).__name__
            error_message = str(e)
            
            logger.error(
                "Failed to create media container",
                error=error_message,
                error_code=error_code,
                error_subcode=error_subcode,
                media_url=media_url,
                error_type=error_type,
            )
            
            # If error 9004 or 2207067, provide more helpful error message
            if error_code == 9004 or error_subcode == 2207067:
                is_video = media_url and any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm'])
                is_reels = params.get("media_type") == "REELS"
                is_own_server = media_url and _is_own_server_url(media_url)
                
                if is_own_server:
                    # URL is from user's own server - focus on BASE_URL configuration
                    base_url = os.getenv("BASE_URL") or os.getenv("APP_URL") or "not set"
                    solution = (
                        f"SOLUTION: Your video is hosted on your own server, but Instagram cannot access it.\n"
                        f"\n"
                        f"✅ CHECK THESE:\n"
                        f"1) BASE_URL/APP_URL is set correctly: {base_url}\n"
                        f"2) Your server is publicly accessible via HTTPS (Instagram requires HTTPS)\n"
                        f"3) The upload URL is reachable: Try opening {media_url} in a browser\n"
                        f"4) No firewall/security blocking Instagram's crawler\n"
                        f"5) Server allows direct file access (no authentication required)\n"
                        f"\n"
                        f"💡 TIP: In production, set BASE_URL to your public HTTPS domain:\n"
                        f"   export BASE_URL=https://yourdomain.com\n"
                        f"   Then restart the app. Upload URLs will use this domain."
                    )
                elif is_video or is_reels:
                    # Video/reels from external URL - but user wants own server, so suggest that first
                    media_type_name = "reels" if is_reels else "video"
                    solution = (
                        f"SOLUTION for {media_type_name.upper()} posts:\n"
                        f"\n"
                        f"✅ OPTION 1: Use your own server (recommended)\n"
                        f"1) Upload the file using 'Upload file' in InstaForge\n"
                        f"2) Set BASE_URL (or APP_URL) to your public HTTPS domain\n"
                        f"3) Ensure your server is publicly accessible\n"
                        f"4) The upload URL will be served from your server\n"
                        f"\n"
                        f"✅ OPTION 2: Use external hosting (if own server not available)\n"
                        f"1) Upload to Cloudinary, AWS S3, or Firebase Storage\n"
                        f"2) Copy the direct HTTPS URL\n"
                        f"3) Use 'Post by URL' and paste the URL\n"
                        f"\n"
                        f"❌ DO NOT USE:\n"
                        f"• Cloudflare tunnels (trycloudflare.com) - unreliable\n"
                        f"• Ngrok - unreliable\n"
                        f"• Localhost URLs - Instagram cannot access them"
                    )
                else:
                    solution = (
                        "SOLUTION: Ensure the URL is publicly accessible via HTTPS.\n"
                        "For your own server, set BASE_URL to your public domain."
                    )
                # Check if it's a Cloudinary URL and provide specific guidance
                is_cloudinary = "cloudinary.com" in (media_url or "").lower()
                cloudinary_tip = ""
                if is_cloudinary:
                    cloudinary_tip = (
                        f"\n💡 Cloudinary URL tips:\n"
                        f"• Ensure the URL is a direct video link (ends with .mp4/.mov)\n"
                        f"• Use the 'Upload' URL format, not 'Fetch' or 'Transform'\n"
                        f"• Check if the video is set to 'Public' in Cloudinary dashboard\n"
                        f"• Try accessing the URL in a browser - it should download/play the video directly\n"
                    )
                
                raise InstagramAPIError(
                    f"Instagram cannot access the media URL (error {error_code}/{error_subcode}).\n"
                    f"This usually means:\n"
                    f"1) The URL is not publicly accessible\n"
                    f"2) The server is blocking Instagram's bot/crawler\n"
                    f"3) The URL is returning HTML instead of the media file\n"
                    f"4) The server requires authentication or has CORS restrictions\n"
                    f"{cloudinary_tip}"
                    f"\n"
                    f"{solution}\n"
                    f"\n"
                    f"URL: {media_url}\n"
                    f"Original error: {error_type}: {error_message} (code: {error_code})",
                    error_code=error_code,
                    error_subcode=error_subcode,
                )
            # Timeout -2 / 2207003: Instagram timed out fetching/processing media (often video/reels)
            if error_code == -2 or error_subcode == 2207003:
                is_reels = params.get("media_type") == "REELS"
                media_type_name = "reels" if is_reels else "video"
                is_own_server = media_url and _is_own_server_url(media_url)
                
                if is_own_server:
                    solution = (
                        f"✅ SOLUTION for your own server:\n"
                        f"• Ensure your server has fast, stable internet connection\n"
                        f"• Check if the video file is too large (max 1GB)\n"
                        f"• Verify the upload URL is directly accessible (no redirects)\n"
                        f"• For reels: Video must be 3-15 minutes, 9:16 aspect ratio, MP4/MOV\n"
                        f"• Consider optimizing video file size if connection is slow"
                    )
                else:
                    solution = (
                        f"✅ SOLUTION:\n"
                        f"• Use your own server (set BASE_URL) or a fast CDN\n"
                        f"• Ensure video URL is direct (no redirects, no authentication)\n"
                        f"• For reels: Video must be 3-15 minutes, 9:16 aspect ratio, MP4/MOV format\n"
                        f"• Maximum file size: 1GB"
                    )
                raise InstagramAPIError(
                    f"Instagram timed out fetching/processing the {media_type_name} (error {error_code}/{error_subcode}).\n"
                    f"\n"
                    f"This usually means:\n"
                    f"1) The video file is too large or takes too long to download\n"
                    f"2) The hosting service is too slow for Instagram's crawler\n"
                    f"3) The video URL is not directly accessible (requires authentication/redirects)\n"
                    f"\n"
                    f"{solution}\n"
                    f"\n"
                    f"URL: {media_url}\n"
                    f"Original error: {str(e)}",
                    error_code=error_code,
                    error_subcode=error_subcode,
                )
            # Aspect ratio error 36003 / 2207009: Media dimensions not supported by Instagram
            if error_code == 36003 or error_subcode == 2207009:
                media_type_name = params.get("media_type", "media")
                if media_type_name == "REELS":
                    aspect_help = (
                        f"Reels require 9:16 aspect ratio (vertical), min 3 seconds, max 15 minutes, MP4/MOV.\n"
                        f"Use 1080×1920 or 720×1280 for best results."
                    )
                elif media_type_name == "STORIES":
                    aspect_help = (
                        f"Stories require 9:16 aspect ratio (vertical).\n"
                        f"Use 1080×1920 or 720×1280."
                    )
                elif media_type_name == "VIDEO":
                    aspect_help = (
                        f"Video posts: Use 1:1 (square) or 4:5 aspect ratio.\n"
                        f"Avoid very wide (e.g. 16:9) or very tall formats."
                    )
                else:
                    aspect_help = (
                        f"Images: Use 1:1 (square), 4:5, or 1.91:1 aspect ratio.\n"
                        f"Carousel items: Each image/video must follow supported aspect ratios."
                    )
                raise InstagramAPIError(
                    f"The aspect ratio of your media is not supported by Instagram (error {error_code}/{error_subcode}).\n"
                    f"\n"
                    f"Supported formats:\n"
                    f"{aspect_help}\n"
                    f"\n"
                    f"Resize or crop your media and try again.\n"
                    f"Original error: {error_type}: {error_message}",
                    error_code=error_code,
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
            MediaURLUnavailableError: If URL returns 404, HTML, or non-media (no retry).
            InstagramAPIError: On timeout or connection errors (retried by caller).
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
            
            # Check if we got a successful response (fail fast, no retry)
            if status_code != 200:
                logger.error(
                    "Media URL verification failed",
                    url=url,
                    status_code=status_code,
                    content_type=content_type,
                    headers=dict(response.headers),
                )
                raise MediaURLUnavailableError(
                    f"Media URL returned status {status_code} instead of 200. "
                    f"This means Instagram's crawler cannot access the URL. "
                    f"Check: 1) File exists on server, 2) Apache is proxying /uploads/ correctly, "
                    f"3) File permissions allow read access. "
                    f"URL: {url}",
                )
            
            # Verify Content-Type header
            is_image = any(ct in content_type for ct in ["image/jpeg", "image/png", "image/gif", "image/webp"])
            is_video = any(ct in content_type for ct in ["video/mp4", "video/quicktime"])
            
            # If Content-Type is text/html, the server is likely returning an error page (fail fast, no retry)
            if "text/html" in content_type:
                try:
                    response_body = response.text[:500]
                    logger.error(
                        "Media URL returns HTML instead of media",
                        url=url,
                        content_type=content_type,
                        response_preview=response_body,
                    )
                except Exception:
                    pass
                raise MediaURLUnavailableError(
                    f"Media URL is returning HTML instead of an image/video. "
                    f"This usually means: 1) Apache is returning an error page, 2) File doesn't exist, "
                    f"3) Apache proxy is misconfigured. "
                    f"Content-Type: {content_type}. "
                    f"Check Apache logs and verify file exists. "
                    f"URL: {url}",
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
                raise MediaURLUnavailableError(
                    f"Media URL GET request returned status {response_get.status_code}. "
                    f"Instagram cannot access media from this URL. "
                    f"URL: {url}",
                )
            # Read first few bytes to check if it's actually binary/image data
            chunk = next(response_get.iter_content(chunk_size=1024), b"")
            response_get.close()
            # Check if content looks like HTML (starts with <) or text (fail fast, no retry)
            if chunk.startswith(b"<") or chunk.startswith(b"<!DOCTYPE") or chunk.startswith(b"<html"):
                raise MediaURLUnavailableError(
                    f"Media URL is returning HTML/text instead of binary image/video data. "
                    f"Cloudflare or the server is likely blocking Instagram's bot. "
                    f"URL: {url}",
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
            # Check if it's a connection error (DNS, network, etc.)
            error_str = str(e).lower()
            if "dns" in error_str or "resolve" in error_str or "connection" in error_str:
                raise InstagramAPIError(
                    f"Media URL is not accessible: {str(e)}. "
                    f"This usually means the domain is unreachable or DNS is failing. "
                    f"URL: {url}",
                    error_code=9004,
                )
            else:
                raise InstagramAPIError(
                    f"Media URL verification failed: {str(e)}. "
                    f"Instagram will verify the URL itself when posting. "
                    f"URL: {url}",
                    error_code=9004,
                )
        except MediaURLUnavailableError:
            raise
        except InstagramAPIError:
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
        """Check the status of a media container (status_code and status for error details)."""
        return self._make_request(
            "GET", f"{container_id}",
            params={"fields": "status_code,status"},
        )
    
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
            recipient_username: Username of recipient (for identification; can be empty if recipient_id set)
            message: Message text to send
            recipient_id: Optional Instagram-scoped user ID (IGSID); prefer over username when available
            
        Returns:
            Result dictionary with status and dm_id
        """
        username = (recipient_username or "").strip() or None
        ig_id = (recipient_id or "").strip() or None
        if not username and not ig_id:
            return {
                "status": "failed",
                "error": "Recipient required: provide recipient_username or recipient_id (comment from.id).",
                "error_code": None,
                "recipient": None,
            }
        
        try:
            account_info = self.get_account_info()
            account_id = account_info.get("id")
            endpoint = f"{account_id}/messages"
            recipient = {"id": ig_id} if ig_id else {"username": username}
            
            response = self._make_request(
                "POST",
                endpoint,
                data={
                    "recipient": recipient,
                    "message": {"text": message},
                }
            )
            
            logger.info(
                "DM sent via Instagram Graph API",
                recipient_username=username,
                recipient_id=ig_id,
                message_length=len(message),
            )
            
            return {
                "status": "success",
                "dm_id": response.get("id") or response.get("message_id"),
                "recipient": username or ig_id,
            }
            
        except InstagramAPIError as e:
            error_code = getattr(e, 'error_code', None)
            
            if error_code == 10:
                logger.warning(
                    "DM failed: Instagram 24-hour messaging window. User must message you first; "
                    "commenting on a post does NOT open DMs. (code 10)",
                    recipient_username=username,
                    recipient_id=ig_id,
                    error_code=error_code,
                    error=str(e),
                )
            elif error_code in [100, 200]:
                logger.warning(
                    "DM failed - may require instagram_manage_messages, or user not found",
                    recipient_username=username,
                    recipient_id=ig_id,
                    error_code=error_code,
                    error=str(e),
                )
            
            return {
                "status": "failed",
                "error": str(e),
                "error_code": error_code,
                "recipient": username or ig_id,
            }