"""State manager for account lifecycle and warm-up progression"""

import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class AccountState(str, Enum):
    """Account lifecycle states"""
    INACTIVE = "inactive"
    CONNECTING = "connecting"
    WARMUP_DAY_1 = "warmup_day_1"
    WARMUP_DAY_2 = "warmup_day_2"
    WARMUP_DAY_3 = "warmup_day_3"
    WARMUP_DAY_4 = "warmup_day_4"
    WARMUP_DAY_5 = "warmup_day_5"
    WARMUP_DAY_6 = "warmup_day_6"
    WARMUP_DAY_7 = "warmup_day_7"
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    ERROR = "error"


class WarmupState:
    """Warm-up state for an account"""
    
    def __init__(
        self,
        account_id: str,
        current_day: int = 0,
        started_at: Optional[datetime] = None,
        actions_today: Dict[str, int] = None,
        last_action_time: Optional[datetime] = None,
        total_actions: int = 0,
    ):
        self.account_id = account_id
        self.current_day = current_day
        self.started_at = started_at or datetime.utcnow()
        self.actions_today = actions_today or {}
        self.last_action_time = last_action_time
        self.total_actions = total_actions
        self.last_reset_date = datetime.utcnow().date()
    
    def get_account_state(self) -> AccountState:
        """Get current account state based on warm-up day"""
        if self.current_day == 0:
            return AccountState.INACTIVE
        elif self.current_day == 1:
            return AccountState.WARMUP_DAY_1
        elif self.current_day == 2:
            return AccountState.WARMUP_DAY_2
        elif self.current_day == 3:
            return AccountState.WARMUP_DAY_3
        elif self.current_day == 4:
            return AccountState.WARMUP_DAY_4
        elif self.current_day == 5:
            return AccountState.WARMUP_DAY_5
        elif self.current_day == 6:
            return AccountState.WARMUP_DAY_6
        elif self.current_day == 7:
            return AccountState.WARMUP_DAY_7
        elif self.current_day > 7:
            return AccountState.ACTIVE
        else:
            return AccountState.INACTIVE
    
    def should_progress_to_next_day(self) -> bool:
        """Check if account should progress to next warm-up day"""
        today = datetime.utcnow().date()
        days_since_start = (today - self.started_at.date()).days
        
        # Progress if it's been at least 1 day since start or last progression
        return days_since_start >= self.current_day and self.current_day < 7
    
    def reset_daily_counters(self):
        """Reset daily action counters (call at start of new day)"""
        today = datetime.utcnow().date()
        if today > self.last_reset_date:
            self.actions_today = {}
            self.last_reset_date = today
            logger.debug(
                "Reset daily counters",
                account_id=self.account_id,
                previous_date=self.last_reset_date.isoformat(),
                new_date=today.isoformat(),
            )
    
    def increment_action(self, action_type: str):
        """Increment counter for an action type"""
        self.reset_daily_counters()  # Ensure we're on current day
        
        if action_type not in self.actions_today:
            self.actions_today[action_type] = 0
        self.actions_today[action_type] += 1
        self.total_actions += 1
        self.last_action_time = datetime.utcnow()
    
    def get_actions_today(self, action_type: Optional[str] = None) -> int:
        """Get number of actions today, optionally filtered by type"""
        self.reset_daily_counters()
        if action_type:
            return self.actions_today.get(action_type, 0)
        return sum(self.actions_today.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "account_id": self.account_id,
            "current_day": self.current_day,
            "started_at": self.started_at.isoformat(),
            "actions_today": self.actions_today,
            "last_action_time": self.last_action_time.isoformat() if self.last_action_time else None,
            "total_actions": self.total_actions,
            "last_reset_date": self.last_reset_date.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WarmupState":
        """Create from dictionary"""
        return cls(
            account_id=data["account_id"],
            current_day=data.get("current_day", 0),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            actions_today=data.get("actions_today", {}),
            last_action_time=datetime.fromisoformat(data["last_action_time"]) if data.get("last_action_time") else None,
            total_actions=data.get("total_actions", 0),
        )


class StateManager:
    """
    Manages account state, warm-up progression, and lifecycle tracking.
    
    Features:
    - Persistent state storage
    - Warm-up day progression
    - Daily action tracking
    - Account lifecycle management
    - State recovery on restart
    """
    
    def __init__(self, state_dir: str = "data/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.warmup_states: Dict[str, WarmupState] = {}
        self.account_states: Dict[str, AccountState] = {}
        self._load_all_states()
    
    def _get_state_file_path(self, account_id: str) -> Path:
        """Get path to state file for an account"""
        return self.state_dir / f"{account_id}.json"
    
    def _load_all_states(self):
        """Load all account states from disk"""
        if not self.state_dir.exists():
            return
        
        for state_file in self.state_dir.glob("*.json"):
            try:
                account_id = state_file.stem
                with open(state_file, "r") as f:
                    data = json.load(f)
                    warmup_state = WarmupState.from_dict(data)
                    self.warmup_states[account_id] = warmup_state
                    self.account_states[account_id] = warmup_state.get_account_state()
                    logger.debug("Loaded account state", account_id=account_id, state=warmup_state.get_account_state().value)
            except Exception as e:
                logger.warning("Failed to load state file", file=str(state_file), error=str(e))
    
    def get_warmup_state(self, account_id: str) -> WarmupState:
        """Get warm-up state for an account, creating if doesn't exist"""
        if account_id not in self.warmup_states:
            self.warmup_states[account_id] = WarmupState(account_id=account_id)
            self._save_state(account_id)
        
        return self.warmup_states[account_id]
    
    def get_account_state(self, account_id: str) -> AccountState:
        """Get current account state"""
        if account_id not in self.account_states:
            warmup_state = self.get_warmup_state(account_id)
            self.account_states[account_id] = warmup_state.get_account_state()
        return self.account_states[account_id]
    
    def start_warmup(self, account_id: str) -> WarmupState:
        """Start warm-up process for an account"""
        warmup_state = self.get_warmup_state(account_id)
        if warmup_state.current_day == 0:
            warmup_state.current_day = 1
            warmup_state.started_at = datetime.utcnow()
            self.account_states[account_id] = warmup_state.get_account_state()
            self._save_state(account_id)
            logger.info("Warm-up started", account_id=account_id, day=1)
        return warmup_state
    
    def progress_warmup_day(self, account_id: str) -> bool:
        """
        Progress account to next warm-up day if conditions are met
        
        Returns:
            True if progression occurred
        """
        warmup_state = self.get_warmup_state(account_id)
        
        if warmup_state.should_progress_to_next_day():
            old_day = warmup_state.current_day
            warmup_state.current_day += 1
            self.account_states[account_id] = warmup_state.get_account_state()
            self._save_state(account_id)
            logger.info(
                "Warm-up day progressed",
                account_id=account_id,
                old_day=old_day,
                new_day=warmup_state.current_day,
            )
            return True
        
        return False
    
    def increment_action(self, account_id: str, action_type: str):
        """Increment action counter for an account"""
        warmup_state = self.get_warmup_state(account_id)
        warmup_state.increment_action(action_type)
        self._save_state(account_id)
    
    def get_warmup_day(self, account_id: str) -> int:
        """Get current warm-up day for an account"""
        return self.get_warmup_state(account_id).current_day
    
    def set_account_state(self, account_id: str, state: AccountState):
        """Manually set account state (for pause/suspend/etc)"""
        self.account_states[account_id] = state
        logger.info("Account state changed", account_id=account_id, state=state.value)
    
    def _save_state(self, account_id: str):
        """Save state to disk"""
        if account_id not in self.warmup_states:
            return
        
        warmup_state = self.warmup_states[account_id]
        state_file = self._get_state_file_path(account_id)
        
        try:
            with open(state_file, "w") as f:
                json.dump(warmup_state.to_dict(), f, indent=2)
        except Exception as e:
            logger.error("Failed to save state", account_id=account_id, error=str(e))
