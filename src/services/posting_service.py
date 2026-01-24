"""Automated posting service for multiple accounts"""

import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from tenacity import RetryError

from ..models.post import Post, PostStatus, PostMedia
from .account_service import AccountService
from ..utils.logger import get_logger
from ..utils.exceptions import PostingError, InstagramAPIError
from ..api.instagram_client import InstagramClient

logger = get_logger(__name__)


class PostingService:
    """Service for automated posting to multiple Instagram accounts"""
    
    def __init__(
        self,
        account_service: AccountService,
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
    ):
        self.account_service = account_service
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
    
    def _upload_media_to_instagram(
        self,
        client: InstagramClient,
        media: PostMedia,
    ) -> str:
        """
        Upload media to Instagram and get container ID
        
        Args:
            client: Instagram API client
            media: Media to upload
            
        Returns:
            Container ID
        """
        if media.media_type == "image":
            if not media.url:
                raise PostingError("Image URL is required for image posts")
            return client.create_media_container(
                image_url=str(media.url),
                caption=media.caption or "",
            )
        
        elif media.media_type == "video":
            if not media.url:
                raise PostingError("Video URL is required for video posts")
            return client.create_media_container(
                video_url=str(media.url),
                caption=media.caption or "",
            )
        
        elif media.media_type == "carousel":
            if not media.children:
                raise PostingError("Carousel posts require child media")
            
            # Instagram requires 2-10 items for carousel
            if len(media.children) < 2:
                raise PostingError(f"Carousel posts require 2-10 media items. You provided {len(media.children)}.")
            if len(media.children) > 10:
                raise PostingError(f"Carousel posts can have maximum 10 items. You provided {len(media.children)}.")
            
            # Create containers for each child
            child_ids = []
            for idx, child in enumerate(media.children, 1):
                logger.info(
                    f"Creating carousel child {idx}/{len(media.children)}",
                    child_type=child.media_type,
                    has_url=bool(child.url),
                )
                child_id = self._upload_media_to_instagram(client, child)
                child_ids.append(child_id)
                # Small delay between child creations
                if idx < len(media.children):
                    time.sleep(1)
            
            # Wait for children to be ready before creating carousel
            logger.info("Waiting for carousel children to be ready", child_count=len(child_ids))
            time.sleep(3)
            
            return client.create_carousel_container(
                children=child_ids,
                caption=media.caption or "",
            )
        
        else:
            raise PostingError(f"Unsupported media type: {media.media_type}")
    
    def _publish_post(
        self,
        client: InstagramClient,
        container_id: str,
        post: Post,
    ) -> Dict[str, Any]:
        """
        Publish a post from container ID
        
        Args:
            client: Instagram API client
            container_id: Media container ID
            post: Post model
            
        Returns:
            Published media information
        """
        # Check container status before publishing
        status = client.get_media_status(container_id)
        
        if status.get("status_code") != "FINISHED":
            logger.warning(
                "Container not ready, waiting",
                container_id=container_id,
                status=status.get("status_code"),
            )
            time.sleep(3)
        
        # Publish the media
        result = client.publish_media(container_id)
        
        logger.info(
            "Post published successfully",
            account_id=post.account_id,
            instagram_media_id=result.get("id"),
        )
        
        return result
    
    def create_post(
        self,
        account_id: str,
        media: PostMedia,
        caption: str = "",
        location_id: Optional[str] = None,
        user_tags: Optional[List[str]] = None,
        scheduled_time: Optional[datetime] = None,
    ) -> Post:
        """
        Create a new post (does not publish immediately)
        
        Args:
            account_id: Target account ID
            media: Media to post
            caption: Post caption
            location_id: Optional location ID
            user_tags: Optional user tags
            scheduled_time: Optional scheduled publish time
            
        Returns:
            Post instance
        """
        account = self.account_service.get_account(account_id)
        
        post = Post(
            account_id=account_id,
            media=media,
            caption=caption,
            location_id=location_id,
            user_tags=user_tags or [],
            scheduled_time=scheduled_time,
            status=PostStatus.PENDING if not scheduled_time else PostStatus.SCHEDULED,
        )
        
        logger.info(
            "Post created",
            account_id=account_id,
            post_id=post.post_id,
            media_type=media.media_type,
            scheduled=scheduled_time is not None,
        )
        
        return post
    
    def publish_post(self, post: Post) -> Post:
        """
        Publish a post to Instagram
        
        Args:
            post: Post to publish
            
        Returns:
            Updated post with published information
            
        Raises:
            PostingError: If posting fails
        """
        if post.status == PostStatus.PUBLISHED:
            raise PostingError("Post is already published")
        
        if post.status == PostStatus.UPLOADING:
            raise PostingError("Post is currently being uploaded")
        
        account = self.account_service.get_account(post.account_id)
        client = self.account_service.get_client(post.account_id)
        
        post.status = PostStatus.UPLOADING
        
        try:
            # Build full caption with hashtags
            full_caption = post.caption
            if post.hashtags:
                hashtag_text = " ".join(f"#{tag}" for tag in post.hashtags)
                full_caption = f"{full_caption}\n\n{hashtag_text}" if full_caption else hashtag_text
            
            # Update media caption if needed
            post.media.caption = full_caption
            
            # Upload media and get container ID
            container_id = self._upload_media_to_instagram(client, post.media)
            
            # Wait for container to be ready (for videos)
            if post.media.media_type == "video":
                logger.info("Waiting for video processing", container_id=container_id)
                time.sleep(5)
            
            # Publish the post
            result = self._publish_post(client, container_id, post)
            
            # Update post with published information
            post.status = PostStatus.PUBLISHED
            post.instagram_media_id = result.get("id")
            post.published_at = datetime.utcnow()
            
            logger.info(
                "Post published successfully",
                account_id=post.account_id,
                username=account.username,
                instagram_media_id=post.instagram_media_id,
            )
            
            return post
        
        except RetryError as e:
            # Extract the underlying exception from RetryError
            error_msg = str(e)
            
            # Try to extract the actual exception from RetryError
            if hasattr(e, 'last_attempt') and e.last_attempt is not None:
                try:
                    underlying_error = e.last_attempt.exception()
                    error_msg = str(underlying_error)
                    
                    # If the underlying error has more details, use those
                    if isinstance(underlying_error, InstagramAPIError):
                        error_code = getattr(underlying_error, 'error_code', None)
                        error_subcode = getattr(underlying_error, 'error_subcode', None)
                        if error_code:
                            error_msg = f"{error_msg} (code: {error_code}, subcode: {error_subcode})"
                except Exception:
                    # If we can't extract the exception, use the RetryError message
                    pass
            
            post.status = PostStatus.FAILED
            post.error_message = error_msg
            
            logger.error(
                "Post publishing failed",
                account_id=post.account_id,
                error=error_msg,
                post_id=post.post_id,
                retry_error=True,
            )
            
            raise PostingError(f"Failed to publish post: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            post.status = PostStatus.FAILED
            post.error_message = error_msg
            
            logger.error(
                "Post publishing failed",
                account_id=post.account_id,
                error=error_msg,
                post_id=post.post_id,
            )
            
            raise PostingError(f"Failed to publish post: {error_msg}")
    
    def publish_post_with_retry(self, post: Post) -> Post:
        """
        Publish a post with automatic retry logic
        
        Args:
            post: Post to publish
            
        Returns:
            Updated post
        """
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.publish_post(post)
            
            except PostingError as e:
                last_error = e
                logger.warning(
                    "Post publish attempt failed, retrying",
                    account_id=post.account_id,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(e),
                )
                
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_seconds * attempt)
                else:
                    break
        
        raise PostingError(f"Failed to publish post after {self.max_retries} attempts: {str(last_error)}")
    
    def publish_to_multiple_accounts(
        self,
        account_ids: List[str],
        media: PostMedia,
        caption: str = "",
        location_id: Optional[str] = None,
    ) -> List[Post]:
        """
        Publish the same post to multiple accounts
        
        Args:
            account_ids: List of account IDs to post to
            media: Media to post
            caption: Post caption
            location_id: Optional location ID
            
        Returns:
            List of published posts
        """
        posts = []
        
        for account_id in account_ids:
            try:
                post = self.create_post(
                    account_id=account_id,
                    media=media,
                    caption=caption,
                    location_id=location_id,
                )
                
                published_post = self.publish_post_with_retry(post)
                posts.append(published_post)
                
                # Add delay between account posts to avoid rate limiting
                if account_id != account_ids[-1]:
                    time.sleep(2)
            
            except Exception as e:
                logger.error(
                    "Failed to publish to account",
                    account_id=account_id,
                    error=str(e),
                )
                # Continue with other accounts even if one fails
        
        return posts
