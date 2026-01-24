"""Daily activity limit enforcement"""

from typing import Dict, Optional
from datetime import datetime, date
from collections import defaultdict
from threading import Lock

from ..utils.logger import get_logger

logger = get_logger(__name__)


class DailyLimits:
    """
    Enforces daily activity limits per account and action type.
    
    Features:
    - Per-account daily limits
    - Per-action-type daily limits
    - Automatic reset at midnight
    - Progressive limits during warm-up
    """
    
    def __init__(
        self,
        default_daily_limit: int = 100,
        action_type_limits: Optional[Dict[str, int]] = None,
    ):
        self.default_daily_limit = default_daily_limit
        self.action_type_limits = action_type_limits or {}
        
        # Track daily action counts
        # Structure: account_id -> action_type -> count
        self.account_action_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.account_daily_totals: Dict[str, int] = defaultdict(int)
        
        # Track which date the counts are for
        self.count_date: Dict[str, date] = {}
        
        # Per-account daily limits
        self.account_limits: Dict[str, int] = {}
        
        self.lock = Lock()
    
    def set_account_limit(self, account_id: str, limit: int):
        """Set daily action limit for an account"""
        self.account_limits[account_id] = limit
    
    def set_action_type_limit(self, action_type: str, limit: int):
        """Set daily limit for an action type"""
        self.action_type_limits[action_type] = limit
    
    def _reset_if_new_day(self, account_id: str):
        """Reset counters if it's a new day"""
        today = date.today()
        
        if account_id not in self.count_date or self.count_date[account_id] != today:
            self.account_action_counts[account_id] = defaultdict(int)
            self.account_daily_totals[account_id] = 0
            self.count_date[account_id] = today
            logger.debug("Reset daily counters", account_id=account_id, date=today.isoformat())
    
    def can_execute(
        self,
        account_id: str,
        action_type: str,
        custom_limit: Optional[int] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if action can be executed within daily limits
        
        Args:
            account_id: Account identifier
            action_type: Type of action
            custom_limit: Optional custom limit override
            
        Returns:
            Tuple of (allowed, reason_if_not_allowed)
        """
        with self.lock:
            self._reset_if_new_day(account_id)
            
            # Determine limit
            limit = custom_limit
            
            # Check action-type limit
            if limit is None and action_type in self.action_type_limits:
                limit = self.action_type_limits[action_type]
            
            # Check account-specific limit
            if limit is None and account_id in self.account_limits:
                limit = self.account_limits[account_id]
            
            # Use default limit
            if limit is None:
                limit = self.default_daily_limit
            
            # Check per-action-type count
            action_count = self.account_action_counts[account_id][action_type]
            if action_count >= limit:
                return False, f"daily_limit_reached_{action_type}"
            
            # Check total daily count (optional - can be disabled)
            # total_count = self.account_daily_totals[account_id]
            # if total_count >= limit * 2:  # Allow more total actions than per-type
            #     return False, "daily_total_limit_reached"
            
            return True, None
    
    def record_action(self, account_id: str, action_type: str):
        """Record that an action was executed"""
        with self.lock:
            self._reset_if_new_day(account_id)
            
            self.account_action_counts[account_id][action_type] += 1
            self.account_daily_totals[account_id] += 1
    
    def get_remaining_actions(
        self,
        account_id: str,
        action_type: str,
        custom_limit: Optional[int] = None,
    ) -> int:
        """Get remaining actions available for today"""
        with self.lock:
            self._reset_if_new_day(account_id)
            
            # Determine limit (same logic as can_execute)
            limit = custom_limit
            if limit is None and action_type in self.action_type_limits:
                limit = self.action_type_limits[action_type]
            if limit is None and account_id in self.account_limits:
                limit = self.account_limits[account_id]
            if limit is None:
                limit = self.default_daily_limit
            
            used = self.account_action_counts[account_id][action_type]
            return max(0, limit - used)
    
    def get_daily_stats(self, account_id: str) -> Dict[str, any]:
        """Get daily statistics for an account"""
        with self.lock:
            self._reset_if_new_day(account_id)
            
            return {
                "account_id": account_id,
                "date": self.count_date.get(account_id, date.today()).isoformat(),
                "total_actions": self.account_daily_totals[account_id],
                "actions_by_type": dict(self.account_action_counts[account_id]),
            }
