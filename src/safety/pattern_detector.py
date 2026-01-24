"""Pattern detection for abnormal behavior"""

from typing import Dict, List, Optional
from collections import deque
from datetime import datetime, timedelta
from threading import Lock

from ..utils.logger import get_logger

logger = get_logger(__name__)


class PatternDetector:
    """
    Detects abnormal patterns in account activity.
    
    Detects:
    - Repetitive actions
    - Unusually high velocity
    - Unusual timing patterns
    - Bot-like behavior
    """
    
    def __init__(
        self,
        velocity_threshold: int = 50,  # Actions per minute
        repetition_threshold: int = 10,  # Same action repeated
        time_window_minutes: int = 5,
    ):
        self.velocity_threshold = velocity_threshold
        self.repetition_threshold = repetition_threshold
        self.time_window_minutes = time_window_minutes
        
        # Track recent actions per account
        # Structure: account_id -> deque of (timestamp, action_type)
        self.account_action_history: Dict[str, deque] = {}
        
        self.lock = Lock()
    
    def record_action(self, account_id: str, action_type: str):
        """Record an action for pattern analysis"""
        with self.lock:
            if account_id not in self.account_action_history:
                self.account_action_history[account_id] = deque(maxlen=1000)
            
            now = datetime.utcnow()
            self.account_action_history[account_id].append((now, action_type))
            
            # Clean old entries (outside time window)
            cutoff = now - timedelta(minutes=self.time_window_minutes)
            history = self.account_action_history[account_id]
            while history and history[0][0] < cutoff:
                history.popleft()
    
    def detect_abnormal_velocity(self, account_id: str) -> tuple[bool, Optional[float]]:
        """
        Detect if account is executing actions at abnormally high velocity
        
        Returns:
            Tuple of (is_abnormal, actions_per_minute)
        """
        with self.lock:
            if account_id not in self.account_action_history:
                return False, 0.0
            
            history = self.account_action_history[account_id]
            if len(history) < 2:
                return False, 0.0
            
            # Calculate velocity (actions per minute)
            first_time = history[0][0]
            last_time = history[-1][0]
            time_span = (last_time - first_time).total_seconds() / 60.0  # minutes
            
            if time_span < 0.1:  # Less than 6 seconds
                time_span = 0.1  # Minimum to avoid division by zero
            
            actions_per_minute = len(history) / time_span
            
            is_abnormal = actions_per_minute > self.velocity_threshold
            
            if is_abnormal:
                logger.warning(
                    "Abnormal velocity detected",
                    account_id=account_id,
                    actions_per_minute=round(actions_per_minute, 2),
                    threshold=self.velocity_threshold,
                )
            
            return is_abnormal, actions_per_minute
    
    def detect_repetition(self, account_id: str) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Detect if same action is being repeated too frequently
        
        Returns:
            Tuple of (is_abnormal, action_type, repetition_count)
        """
        with self.lock:
            if account_id not in self.account_action_history:
                return False, None, None
            
            history = self.account_action_history[account_id]
            if len(history) < self.repetition_threshold:
                return False, None, None
            
            # Check last N actions for repetition
            recent_actions = [action_type for _, action_type in list(history)[-self.repetition_threshold:]]
            
            # Check if all recent actions are the same
            if len(set(recent_actions)) == 1:
                action_type = recent_actions[0]
                logger.warning(
                    "Repetitive action pattern detected",
                    account_id=account_id,
                    action_type=action_type,
                    repetition_count=self.repetition_threshold,
                )
                return True, action_type, self.repetition_threshold
            
            return False, None, None
    
    def detect_unusual_timing(self, account_id: str) -> tuple[bool, Optional[Dict[str, any]]]:
        """
        Detect unusual timing patterns (e.g., actions at exact intervals)
        
        Returns:
            Tuple of (is_abnormal, pattern_info)
        """
        with self.lock:
            if account_id not in self.account_action_history:
                return False, None
            
            history = self.account_action_history[account_id]
            if len(history) < 5:
                return False, None
            
            # Check intervals between consecutive actions
            intervals = []
            for i in range(1, len(history)):
                interval = (history[i][0] - history[i-1][0]).total_seconds()
                intervals.append(interval)
            
            # Check if intervals are too uniform (bot-like)
            if len(intervals) >= 3:
                avg_interval = sum(intervals) / len(intervals)
                variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
                std_dev = variance ** 0.5
                
                # Low variance indicates uniform timing (bot-like)
                coefficient_of_variation = std_dev / avg_interval if avg_interval > 0 else 0
                
                if coefficient_of_variation < 0.1 and avg_interval < 10:  # Very uniform, fast
                    logger.warning(
                        "Unusual timing pattern detected",
                        account_id=account_id,
                        avg_interval=round(avg_interval, 2),
                        coefficient_of_variation=round(coefficient_of_variation, 3),
                    )
                    return True, {
                        "avg_interval": avg_interval,
                        "coefficient_of_variation": coefficient_of_variation,
                    }
            
            return False, None
    
    def check_patterns(self, account_id: str) -> Dict[str, any]:
        """
        Check all patterns and return summary
        
        Returns:
            Dictionary with pattern detection results
        """
        velocity_abnormal, velocity = self.detect_abnormal_velocity(account_id)
        repetition_abnormal, action_type, count = self.detect_repetition(account_id)
        timing_abnormal, timing_info = self.detect_unusual_timing(account_id)
        
        has_abnormal_pattern = velocity_abnormal or repetition_abnormal or timing_abnormal
        
        return {
            "account_id": account_id,
            "has_abnormal_pattern": has_abnormal_pattern,
            "velocity_abnormal": velocity_abnormal,
            "velocity": round(velocity, 2) if velocity else None,
            "repetition_abnormal": repetition_abnormal,
            "repetitive_action": action_type,
            "repetition_count": count,
            "timing_abnormal": timing_abnormal,
            "timing_info": timing_info,
        }
