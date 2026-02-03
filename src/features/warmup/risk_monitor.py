"""
Risk Monitor - Phase 4
Tracks API errors, login failures, shadowban signals, reach drops.
Auto-pause on 429/190.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from ...utils.logger import get_logger
from .warmup_store import get_warmup_plan, update_warmup_plan
from .day_plans import AUTO_PAUSE_ERROR_CODES

logger = get_logger(__name__)


class RiskMonitor:
    """Monitors account risk during warm-up. Triggers pause on critical events."""

    def __init__(self):
        self._error_counts: Dict[str, List[float]] = defaultdict(list)
        self._login_failures: Dict[str, List[float]] = defaultdict(list)
        self._window_hours = 24
        self._max_errors_per_window = 5
        self._max_login_failures = 2

    def record_api_error(self, account_id: str, error_code: Optional[int] = None) -> Optional[str]:
        """
        Record an API error. Returns pause reason if warm-up should be paused.
        """
        now = time.time()
        key = account_id
        self._error_counts[key].append(now)
        # Trim old
        cutoff = now - (self._window_hours * 3600)
        self._error_counts[key] = [t for t in self._error_counts[key] if t > cutoff]

        if error_code in AUTO_PAUSE_ERROR_CODES:
            return f"API error {error_code} (rate limit or token issue) - warm-up paused"

        if len(self._error_counts[key]) >= self._max_errors_per_window:
            return f"Too many API errors ({len(self._error_counts[key])}) in {self._window_hours}h - warm-up paused"
        return None

    def record_login_failure(self, account_id: str) -> Optional[str]:
        """Record login failure. Returns pause reason if should pause."""
        import time
        now = time.time()
        self._login_failures[account_id].append(now)
        cutoff = now - 3600
        self._login_failures[account_id] = [t for t in self._login_failures[account_id] if t > cutoff]
        if len(self._login_failures[account_id]) >= self._max_login_failures:
            return "Login failures detected - warm-up paused"
        return None

    def record_reach_drop(self, account_id: str, prev_reach: int, new_reach: int) -> Optional[str]:
        """Record significant reach drop (shadowban signal)."""
        if prev_reach > 0 and new_reach < prev_reach * 0.3:
            return f"Reach dropped >70% ({prev_reach} -> {new_reach}) - possible shadowban"
        return None

    def update_risk_score(self, account_id: str, delta: int) -> Optional[Dict[str, Any]]:
        """Update risk score (0-100). If >= 80, recommend pause."""
        plan = get_warmup_plan(account_id)
        if not plan:
            return None
        score = min(100, max(0, plan.get("risk_score", 0) + delta))
        return update_warmup_plan(account_id, {"risk_score": score})

    def should_pause(self, account_id: str) -> Tuple[bool, Optional[str]]:
        """Check if warm-up should be paused. Returns (should_pause, reason)."""
        plan = get_warmup_plan(account_id)
        if not plan or plan.get("status") != "active":
            return False, None
        if plan.get("risk_score", 0) >= 80:
            return True, "Risk score too high"
        return False, None


