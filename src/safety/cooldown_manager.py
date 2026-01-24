"""Cooldown management for action spacing"""

import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from threading import Lock

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CooldownManager:
    """
    Manages cooldown periods between actions.
    
    Features:
    - Per-action-type cooldowns
    - Per-account cooldowns
    - Global cooldowns
    - Exponential backoff on failures
    """
    
    def __init__(self, default_cooldown_seconds: float = 5.0):
        self.default_cooldown_seconds = default_cooldown_seconds
        
        # Track last execution time
        self.global_last_action: Optional[datetime] = None
        self.account_last_action: Dict[str, datetime] = {}
        self.action_type_last_action: Dict[str, datetime] = {}
        self.account_action_type_last_action: Dict[tuple[str, str], datetime] = {}
        
        # Cooldown durations (can be customized)
        self.action_type_cooldowns: Dict[str, float] = {}
        self.account_cooldowns: Dict[str, float] = {}
        
        # Failure tracking for exponential backoff
        self.account_failure_count: Dict[str, int] = {}
        
        self.lock = Lock()
    
    def set_action_type_cooldown(self, action_type: str, cooldown_seconds: float):
        """Set cooldown duration for an action type"""
        self.action_type_cooldowns[action_type] = cooldown_seconds
    
    def set_account_cooldown(self, account_id: str, cooldown_seconds: float):
        """Set custom cooldown for an account"""
        self.account_cooldowns[account_id] = cooldown_seconds
    
    def get_cooldown_seconds(
        self,
        action_type: str,
        account_id: Optional[str] = None,
    ) -> float:
        """
        Get required cooldown duration for an action
        
        Args:
            action_type: Type of action
            account_id: Optional account identifier
            
        Returns:
            Required cooldown in seconds
        """
        # Start with default
        cooldown = self.default_cooldown_seconds
        
        # Override with action-type specific cooldown
        if action_type in self.action_type_cooldowns:
            cooldown = self.action_type_cooldowns[action_type]
        
        # Override with account-specific cooldown
        if account_id and account_id in self.account_cooldowns:
            cooldown = self.account_cooldowns[account_id]
        
        # Apply exponential backoff if account has recent failures
        if account_id and account_id in self.account_failure_count:
            failure_count = self.account_failure_count[account_id]
            if failure_count > 0:
                backoff_multiplier = min(2.0 ** failure_count, 10.0)  # Cap at 10x
                cooldown *= backoff_multiplier
        
        return cooldown
    
    def can_execute(
        self,
        action_type: str,
        account_id: Optional[str] = None,
    ) -> tuple[bool, float]:
        """
        Check if action can be executed (cooldown expired)
        
        Args:
            action_type: Type of action
            account_id: Optional account identifier
            
        Returns:
            Tuple of (allowed, seconds_until_allowed)
        """
        with self.lock:
            now = datetime.utcnow()
            cooldown_seconds = self.get_cooldown_seconds(action_type, account_id)
            
            # Check global cooldown
            if self.global_last_action:
                time_since = (now - self.global_last_action).total_seconds()
                if time_since < cooldown_seconds:
                    return False, cooldown_seconds - time_since
            
            # Check account-specific cooldown
            if account_id and account_id in self.account_last_action:
                time_since = (now - self.account_last_action[account_id]).total_seconds()
                if time_since < cooldown_seconds:
                    return False, cooldown_seconds - time_since
            
            # Check action-type specific cooldown
            if action_type in self.action_type_last_action:
                time_since = (now - self.action_type_last_action[action_type]).total_seconds()
                if time_since < cooldown_seconds:
                    return False, cooldown_seconds - time_since
            
            # Check account+action-type combination
            if account_id:
                key = (account_id, action_type)
                if key in self.account_action_type_last_action:
                    time_since = (now - self.account_action_type_last_action[key]).total_seconds()
                    if time_since < cooldown_seconds:
                        return False, cooldown_seconds - time_since
            
            return True, 0.0
    
    def record_action(
        self,
        action_type: str,
        account_id: Optional[str] = None,
        success: bool = True,
    ):
        """
        Record that an action was executed
        
        Args:
            action_type: Type of action
            account_id: Optional account identifier
            success: Whether action was successful
        """
        with self.lock:
            now = datetime.utcnow()
            
            self.global_last_action = now
            
            if account_id:
                self.account_last_action[account_id] = now
                
                # Track failures for exponential backoff
                if success:
                    self.account_failure_count[account_id] = 0
                else:
                    if account_id not in self.account_failure_count:
                        self.account_failure_count[account_id] = 0
                    self.account_failure_count[account_id] += 1
            
            self.action_type_last_action[action_type] = now
            
            if account_id:
                self.account_action_type_last_action[(account_id, action_type)] = now
    
    def wait_for_cooldown(
        self,
        action_type: str,
        account_id: Optional[str] = None,
        max_wait_seconds: float = 300.0,
    ) -> bool:
        """
        Wait until cooldown period has expired
        
        Args:
            action_type: Type of action
            account_id: Optional account identifier
            max_wait_seconds: Maximum seconds to wait
            
        Returns:
            True if cooldown expired, False if max wait exceeded
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            allowed, seconds_remaining = self.can_execute(action_type, account_id)
            if allowed:
                return True
            
            # Wait a bit before checking again
            sleep_time = min(seconds_remaining, 5.0)
            time.sleep(sleep_time)
        
        return False
