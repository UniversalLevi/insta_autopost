"""Warming up action interfaces and implementations"""

import time
import random
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.account import Account

from ..utils.logger import get_logger
from ..api.instagram_client import InstagramClient

logger = get_logger(__name__)


class WarmingAction(ABC):
    """Base interface for warming up actions"""
    
    def __init__(self, client: InstagramClient):
        self.client = client
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the warming action
        
        Returns:
            Action result dictionary
        """
        pass
    
    @abstractmethod
    def get_action_name(self) -> str:
        """Get the name of this action"""
        pass


class LikeAction(WarmingAction):
    """Like a post using browser automation
    
    Falls back to simulated if browser automation is not available or fails.
    """
    
    def __init__(self, client, browser_wrapper=None, account=None):
        """
        Initialize like action
        
        Args:
            client: Instagram API client
            browser_wrapper: Optional browser automation wrapper
            account: Optional account model (for username/password)
        """
        super().__init__(client)
        self.browser_wrapper = browser_wrapper
        self.account = account
    
    def execute(self, media_id: str, post_url: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Like a post using browser automation
        
        Args:
            media_id: Instagram media ID to like
            post_url: Optional post URL (if not provided, will try to get from media_id)
            
        Returns:
            Action result
        """
        logger.info(
            "Warming action: Like",
            media_id=media_id,
            has_browser_wrapper=bool(self.browser_wrapper),
        )
        
        # Try browser automation if available
        if self.browser_wrapper and self.account:
            try:
                # Get post URL if not provided
                if not post_url:
                    # Try to get permalink from media info
                    try:
                        # Get media info to extract permalink
                        media_info = self.client._make_request(
                            "GET",
                            media_id,
                            params={"fields": "permalink"}
                        )
                        post_url = media_info.get("permalink")
                    except Exception as e:
                        logger.debug("Could not get permalink from API", error=str(e))
                        # Fallback: construct URL from media ID (may not work)
                        # Instagram URLs format: https://www.instagram.com/p/{shortcode}/
                        post_url = None
                
                if post_url:
                    # Use browser automation to like
                    result = self.browser_wrapper.like_post_sync(
                        account_id=self.account.account_id,
                        post_url=post_url,
                        username=self.account.username,
                        password=getattr(self.account, 'password', None),
                        proxy_url=self.account.proxy.proxy_url if self.account.proxy.enabled else None,
                    )
                    
                    if result.get("status") in ["completed", "already_liked"]:
                        logger.info(
                            "Post liked successfully via browser",
                            media_id=media_id,
                            post_url=post_url,
                            status=result.get("status"),
                        )
                        return {
                            "action": "like",
                            "media_id": media_id,
                            "post_url": post_url,
                            "status": result.get("status"),
                            "method": "browser",
                            "timestamp": time.time(),
                        }
                    else:
                        logger.warning(
                            "Browser like failed, falling back to simulated",
                            media_id=media_id,
                            error=result.get("error"),
                        )
                else:
                    logger.warning(
                        "Could not get post URL, falling back to simulated",
                        media_id=media_id,
                    )
            except Exception as e:
                logger.warning(
                    "Browser automation error, falling back to simulated",
                    media_id=media_id,
                    error=str(e),
                )
        
        # Fallback: Simulated (if browser automation not available or failed)
        logger.warning(
            "Like action using simulated mode (browser automation not available or failed)",
            media_id=media_id,
        )
        
        # Simulate realistic delay
        time.sleep(random.uniform(0.5, 1.5))
        
        return {
            "action": "like",
            "media_id": media_id,
            "status": "simulated",
            "note": "Browser automation not available or failed",
            "timestamp": time.time(),
        }
    
    def get_action_name(self) -> str:
        return "like"


class CommentAction(WarmingAction):
    """Comment on a post using Instagram Graph API"""
    
    def execute(self, media_id: str, comment_text: str, **kwargs) -> Dict[str, Any]:
        """
        Comment on a post
        
        Args:
            media_id: Instagram media ID to comment on
            comment_text: Comment text
            
        Returns:
            Action result
        """
        logger.info(
            "Warming action: Comment",
            media_id=media_id,
            comment_length=len(comment_text),
        )
        
        try:
            # Use Instagram Graph API to comment
            result = self.client.comment_on_media(media_id, comment_text)
            
            logger.info(
                "Comment posted successfully",
                media_id=media_id,
                comment_id=result.get("id"),
            )
            
            return {
                "action": "comment",
                "media_id": media_id,
                "comment_id": result.get("id"),
                "comment_text": comment_text,
                "status": "completed",
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(
                "Failed to post comment",
                media_id=media_id,
                error=str(e),
            )
            return {
                "action": "comment",
                "media_id": media_id,
                "comment_text": comment_text,
                "status": "failed",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    def get_action_name(self) -> str:
        return "comment"


class FollowAction(WarmingAction):
    """Follow a user
    
    Note: Instagram Graph API does not support following users directly.
    This action logs the attempt but does not perform actual API calls.
    """
    
    def execute(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Follow a user
        
        Args:
            user_id: Instagram user ID to follow
            
        Returns:
            Action result
        """
        logger.info(
            "Warming action: Follow",
            user_id=user_id,
        )
        
        # Note: Instagram Graph API doesn't support following users
        # This is a limitation of the API. We log the action for tracking purposes.
        logger.warning(
            "Follow action not supported via Instagram Graph API",
            user_id=user_id,
        )
        
        # Simulate realistic delay
        time.sleep(random.uniform(0.8, 1.5))
        
        return {
            "action": "follow",
            "user_id": user_id,
            "status": "simulated",
            "note": "Instagram Graph API doesn't support following users",
            "timestamp": time.time(),
        }
    
    def get_action_name(self) -> str:
        return "follow"


class StoryViewAction(WarmingAction):
    """View a user's story
    
    Note: Instagram Graph API does not support viewing stories directly.
    This action logs the attempt but does not perform actual API calls.
    """
    
    def execute(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        View a user's story
        
        Args:
            user_id: Instagram user ID whose story to view
            
        Returns:
            Action result
        """
        logger.info(
            "Warming action: Story View",
            user_id=user_id,
        )
        
        # Note: Instagram Graph API doesn't support viewing stories
        # This is a limitation of the API. We log the action for tracking purposes.
        logger.warning(
            "Story view action not supported via Instagram Graph API",
            user_id=user_id,
        )
        
        # Simulate realistic delay
        time.sleep(random.uniform(0.5, 1.0))
        
        return {
            "action": "story_view",
            "user_id": user_id,
            "status": "simulated",
            "note": "Instagram Graph API doesn't support viewing stories",
            "timestamp": time.time(),
        }
    
    def get_action_name(self) -> str:
        return "story_view"


class DMAction(WarmingAction):
    """Send a direct message (placeholder implementation)"""
    
    def execute(self, user_id: str, message_text: str, **kwargs) -> Dict[str, Any]:
        """
        Send a direct message
        
        Args:
            user_id: Instagram user ID to message
            message_text: Message text
            
        Returns:
            Action result
        """
        # TODO: Implement actual Instagram API call for DM
        logger.info(
            "Warming action: Direct Message",
            user_id=user_id,
            message_length=len(message_text),
        )
        
        time.sleep(random.uniform(1.0, 2.0))
        
        return {
            "action": "dm",
            "user_id": user_id,
            "message_text": message_text,
            "status": "completed",
            "timestamp": time.time(),
        }
    
    def get_action_name(self) -> str:
        return "dm"


def create_warming_action(action_type: str, client: InstagramClient) -> WarmingAction:
    """
    Factory function to create warming actions
    
    Args:
        action_type: Type of action (like, comment, follow, story_view, dm)
        client: Instagram API client
        
    Returns:
        WarmingAction instance
    """
    action_map = {
        "like": LikeAction,
        "comment": CommentAction,
        "follow": FollowAction,
        "story_view": StoryViewAction,
        "dm": DMAction,
    }
    
    action_class = action_map.get(action_type.lower())
    if not action_class:
        raise ValueError(f"Unknown warming action type: {action_type}")
    
    return action_class(client)
