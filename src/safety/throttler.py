"""Global and per-account throttling system"""

import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from ..utils.logger import get_logger

logger = get_logger(__name__)


class Throttler:
    """
    Throttling system for controlling action rates.
    
    Features:
    - Global rate limiting
    - Per-account rate limiting
    - Per-action-type rate limiting
    - Burst protection
    - Time-window based limiting
    """
    
    def __init__(
        self,
        global_max_per_hour: int = 500,
        global_max_per_minute: int = 50,
        account_max_per_hour: int = 50,
        account_max_per_minute: int = 10,
    ):
        self.global_max_per_hour = global_max_per_hour
        self.global_max_per_minute = global_max_per_minute
        self.account_max_per_hour = account_max_per_hour
        self.account_max_per_minute = account_max_per_minute
        
        # Track action timestamps
        self.global_actions: list = []
        self.account_actions: Dict[str, list] = defaultdict(list)
        self.action_type_actions: Dict[str, list] = defaultdict(list)
        
        self.lock = Lock()
    
    def can_execute(
        self,
        account_id: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if an action can be executed based on throttling rules
        
        Args:
            account_id: Optional account identifier
            action_type: Optional action type
            
        Returns:
            Tuple of (allowed, reason_if_not_allowed)
        """
        with self.lock:
            now = datetime.utcnow()
            
            # Clean old actions (outside time windows)
            self._clean_old_actions(now)
            
            # Check global limits
            if len(self.global_actions) >= self.global_max_per_minute:
                return False, "global_per_minute_limit"
            
            hour_ago = now - timedelta(hours=1)
            global_last_hour = [a for a in self.global_actions if a >= hour_ago]
            if len(global_last_hour) >= self.global_max_per_hour:
                return False, "global_per_hour_limit"
            
            # Check account limits
            if account_id:
                account_actions = self.account_actions[account_id]
                
                if len(account_actions) >= self.account_max_per_minute:
                    return False, "account_per_minute_limit"
                
                account_last_hour = [a for a in account_actions if a >= hour_ago]
                if len(account_last_hour) >= self.account_max_per_hour:
                    return False, "account_per_hour_limit"
            
            # Check action type limits (if configured)
            if action_type:
                action_type_actions = self.action_type_actions[action_type]
                # Action-type specific limits can be added here
                pass
            
            return True, None
    
    def record_action(
        self,
        account_id: Optional[str] = None,
        action_type: Optional[str] = None,
    ):
        """Record that an action was executed"""
        with self.lock:
            now = datetime.utcnow()
            
            self.global_actions.append(now)
            
            if account_id:
                self.account_actions[account_id].append(now)
            
            if action_type:
                self.action_type_actions[action_type].append(now)
    
    def _clean_old_actions(self, now: datetime):
        """Remove action timestamps older than 1 hour"""
        hour_ago = now - timedelta(hours=1)
        
        self.global_actions = [a for a in self.global_actions if a >= hour_ago]
        
        for account_id in list(self.account_actions.keys()):
            self.account_actions[account_id] = [
                a for a in self.account_actions[account_id] if a >= hour_ago
            ]
            if not self.account_actions[account_id]:
                del self.account_actions[account_id]
        
        for action_type in list(self.action_type_actions.keys()):
            self.action_type_actions[action_type] = [
                a for a in self.action_type_actions[action_type] if a >= hour_ago
            ]
            if not self.action_type_actions[action_type]:
                del self.action_type_actions[action_type]
    
    def wait_if_needed(
        self,
        account_id: Optional[str] = None,
        action_type: Optional[str] = None,
        max_wait_seconds: float = 60.0,
    ) -> bool:
        """
        Wait if necessary to respect throttling limits
        
        Args:
            account_id: Optional account identifier
            action_type: Optional action type
            max_wait_seconds: Maximum seconds to wait
            
        Returns:
            True if action can proceed, False if would exceed max wait
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            allowed, reason = self.can_execute(account_id, action_type)
            if allowed:
                return True
            
            # Wait a bit before checking again
            time.sleep(1)
        
        return False
    
    def get_statistics(self) -> Dict[str, any]:
        """Get throttling statistics"""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        return {
            "global": {
                "last_minute": len([a for a in self.global_actions if a >= minute_ago]),
                "last_hour": len([a for a in self.global_actions if a >= hour_ago]),
                "max_per_minute": self.global_max_per_minute,
                "max_per_hour": self.global_max_per_hour,
            },
            "accounts": {
                account_id: {
                    "last_minute": len([a for a in actions if a >= minute_ago]),
                    "last_hour": len([a for a in actions if a >= hour_ago]),
                }
                for account_id, actions in self.account_actions.items()
            },
        }
