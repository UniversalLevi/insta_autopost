"""Warming up service for daily account activity"""

import time
import random
from typing import List, Dict, Any
from datetime import datetime, time as dt_time

from ..models.account import Account
from ..services.account_service import AccountService
from ..utils.logger import get_logger
from .warming_actions import create_warming_action, WarmingAction

logger = get_logger(__name__)


class WarmingService:
    """Service for daily warming up behavior"""
    
    def __init__(
        self,
        account_service: AccountService,
        schedule_time: str = "09:00",
        randomize_delay_minutes: int = 30,
        action_spacing_seconds: int = 60,
        browser_wrapper=None,
    ):
        self.account_service = account_service
        self.schedule_time = schedule_time
        self.randomize_delay_minutes = randomize_delay_minutes
        self.action_spacing_seconds = action_spacing_seconds
        self.browser_wrapper = browser_wrapper
    
    def _get_target_users(self, account_id: str, count: int = 10) -> List[str]:
        """
        Get target users for warming actions
        
        Attempts to discover users from account's followers or via media interactions.
        In production, this would use Instagram's Business Discovery API or similar.
        
        Args:
            account_id: Account identifier
            count: Number of target users to return
            
        Returns:
            List of user IDs
        """
        logger.debug(
            "Getting target users for warming",
            account_id=account_id,
            count=count,
        )
        
        client = self.account_service.get_client(account_id)
        
        try:
            # Try to get users who interacted with recent media
            # Note: Instagram Graph API has limited access to user discovery
            # This is a best-effort approach
            
            recent_media = client.get_recent_media(limit=5)
            
            # Extract user IDs from media interactions if available
            # Note: This depends on API permissions and may not always work
            user_ids = []
            
            # If we can't get real users, use fallback
            # In production, you'd implement proper user discovery here
            logger.info(
                "Using fallback user discovery for warming actions",
                account_id=account_id,
            )
            
        except Exception as e:
            logger.warning(
                "Failed to get real users for warming, using fallback",
                account_id=account_id,
                error=str(e),
            )
        
        # Fallback: return placeholder IDs
        # In a production system, implement proper user discovery
        # This could use Instagram Business Discovery API, hashtag analysis, etc.
        return [f"user_{i}" for i in range(count)]
    
    def _get_target_media(self, account_id: str, count: int = 10) -> List[str]:
        """
        Get target media for warming actions
        
        Attempts to discover real media from the account's media library
        or via hashtag search for warming actions.
        
        Args:
            account_id: Account identifier
            count: Number of media items to return
            
        Returns:
            List of media IDs
        """
        logger.debug(
            "Getting target media for warming",
            account_id=account_id,
            count=count,
        )
        
        client = self.account_service.get_client(account_id)
        
        try:
            # Get recent media from the account's media library
            # This finds media that we can interact with (comment on, etc.)
            recent_media = client.get_recent_media(limit=count * 2)
            
            if recent_media:
                media_ids = [item["id"] for item in recent_media[:count]]
                logger.info(
                    "Found media for warming actions",
                    account_id=account_id,
                    media_count=len(media_ids),
                )
                return media_ids
            
            logger.warning(
                "No media found for warming actions, using fallback",
                account_id=account_id,
            )
            
        except Exception as e:
            logger.warning(
                "Failed to get real media for warming, using fallback",
                account_id=account_id,
                error=str(e),
            )
        
        # Fallback: return placeholder IDs if we can't get real media
        # In a production system, you might want to use hashtag search
        # or other discovery methods here
        return [f"media_{i}" for i in range(count)]
    
    def execute_warming_for_account(self, account_id: str) -> Dict[str, Any]:
        """
        Execute daily warming actions for an account
        
        Args:
            account_id: Account identifier
            
        Returns:
            Warming execution results
        """
        account = self.account_service.get_account(account_id)
        
        if not account.warming.enabled:
            logger.info(
                "Warming disabled for account",
                account_id=account_id,
            )
            return {
                "account_id": account_id,
                "status": "skipped",
                "reason": "warming_disabled",
            }
        
        client = self.account_service.get_client(account_id)
        
        logger.info(
            "Starting warming actions",
            account_id=account_id,
            username=account.username,
            daily_actions=account.warming.daily_actions,
            action_types=account.warming.action_types,
        )
        
        results = {
            "account_id": account_id,
            "status": "completed",
            "actions_executed": [],
            "started_at": datetime.utcnow().isoformat(),
        }
        
        # Distribute actions across action types
        actions_per_type = account.warming.daily_actions // len(account.warming.action_types)
        remaining_actions = account.warming.daily_actions % len(account.warming.action_types)
        
        for action_type in account.warming.action_types:
            action_count = actions_per_type
            if remaining_actions > 0:
                action_count += 1
                remaining_actions -= 1
            
            try:
                action = create_warming_action(
                    action_type,
                    client,
                    browser_wrapper=self.browser_wrapper,
                    account=account,
                )
                
                for _ in range(action_count):
                    try:
                        # Get targets based on action type
                        if action_type == "like":
                            targets = self._get_target_media(account_id, action_count)
                            target_id = random.choice(targets)
                            # Get post URL if available (from media info)
                            post_url = None
                            try:
                                # Try to get permalink from media
                                media_list = client.get_recent_media(limit=action_count * 2)
                                for media in media_list:
                                    if media.get("id") == target_id:
                                        post_url = media.get("permalink")
                                        break
                            except Exception:
                                pass
                            result = action.execute(media_id=target_id, post_url=post_url)
                        
                        elif action_type == "comment":
                            targets = self._get_target_media(account_id, action_count)
                            target_id = random.choice(targets)
                            comment_text = self._generate_comment()
                            result = action.execute(media_id=target_id, comment_text=comment_text)
                        
                        elif action_type == "follow":
                            targets = self._get_target_users(account_id, action_count)
                            target_id = random.choice(targets)
                            result = action.execute(user_id=target_id)
                        
                        elif action_type == "story_view":
                            targets = self._get_target_users(account_id, action_count)
                            target_id = random.choice(targets)
                            result = action.execute(user_id=target_id)
                        
                        elif action_type == "dm":
                            targets = self._get_target_users(account_id, action_count)
                            target_id = random.choice(targets)
                            message_text = self._generate_dm_message()
                            result = action.execute(user_id=target_id, message_text=message_text)
                        
                        else:
                            logger.warning(
                                "Unknown action type",
                                action_type=action_type,
                            )
                            continue
                        
                        results["actions_executed"].append(result)
                        
                        # Space out actions
                        if action_count > 1:
                            delay = random.uniform(
                                self.action_spacing_seconds * 0.8,
                                self.action_spacing_seconds * 1.2,
                            )
                            time.sleep(delay)
                    
                    except Exception as e:
                        logger.error(
                            "Warming action failed",
                            account_id=account_id,
                            action_type=action_type,
                            error=str(e),
                        )
                        results["actions_executed"].append({
                            "action": action_type,
                            "status": "failed",
                            "error": str(e),
                        })
            
            except Exception as e:
                logger.error(
                    "Failed to create warming action",
                    account_id=account_id,
                    action_type=action_type,
                    error=str(e),
                )
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["total_actions"] = len(results["actions_executed"])
        
        logger.info(
            "Warming actions completed",
            account_id=account_id,
            total_actions=results["total_actions"],
        )
        
        return results
    
    def _generate_comment(self) -> str:
        """Generate a random comment (placeholder)"""
        comments = [
            "Great post! 👍",
            "Love this! ❤️",
            "Amazing content!",
            "So inspiring!",
            "Beautiful! ✨",
        ]
        return random.choice(comments)
    
    def _generate_dm_message(self) -> str:
        """Generate a random DM message (placeholder)"""
        messages = [
            "Hey! Love your content",
            "Hi there! 👋",
            "Great work!",
        ]
        return random.choice(messages)
    
    def execute_warming_for_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """Execute warming actions for all accounts"""
        results = {}
        
        account_ids = [acc.account_id for acc in self.account_service.list_accounts()]
        for account_id in account_ids:
            try:
                results[account_id] = self.execute_warming_for_account(account_id)
            except Exception as e:
                logger.error(
                    "Failed to execute warming for account",
                    account_id=account_id,
                    error=str(e),
                )
                results[account_id] = {
                    "account_id": account_id,
                    "status": "failed",
                    "error": str(e),
                }
        
        return results
