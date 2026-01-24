"""Risk assessment for actions and accounts"""

from typing import Dict, Optional, Any
from datetime import datetime

from ..core.policy_engine import PolicyEngine, ActionType, RiskLevel
from ..core.health_monitor import HealthMonitor
from .pattern_detector import PatternDetector
from .throttler import Throttler
from .daily_limits import DailyLimits
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RiskAssessor:
    """
    Comprehensive risk assessment system.
    
    Combines multiple factors to assess risk:
    - Action type risk profile
    - Account health
    - Pattern detection
    - Throttling status
    - Daily limits
    """
    
    def __init__(
        self,
        policy_engine: PolicyEngine,
        health_monitor: HealthMonitor,
        pattern_detector: PatternDetector,
        throttler: Throttler,
        daily_limits: DailyLimits,
    ):
        self.policy_engine = policy_engine
        self.health_monitor = health_monitor
        self.pattern_detector = pattern_detector
        self.throttler = throttler
        self.daily_limits = daily_limits
    
    def assess_action_risk(
        self,
        account_id: str,
        action_type: ActionType,
        account_warmup_days: int = 0,
    ) -> Dict[str, Any]:
        """
        Comprehensive risk assessment for an action
        
        Args:
            account_id: Account identifier
            action_type: Type of action to assess
            account_warmup_days: Days since warm-up started
            
        Returns:
            Risk assessment dictionary
        """
        # Start with policy engine assessment
        policy_assessment = self.policy_engine.assess_action_risk(
            action_type=action_type,
            account_warmup_days=account_warmup_days,
            account_health_score=self.health_monitor.get_health_score(account_id),
        )
        
        # Check throttling
        can_throttle, throttle_reason = self.throttler.can_execute(
            account_id=account_id,
            action_type=action_type.value,
        )
        
        # Check daily limits
        can_limit, limit_reason = self.daily_limits.can_execute(
            account_id=account_id,
            action_type=action_type.value,
        )
        
        # Check patterns
        pattern_check = self.pattern_detector.check_patterns(account_id)
        
        # Get health status
        health_score = self.health_monitor.get_health_score(account_id)
        health_status = self.health_monitor.get_health_status(account_id)
        
        # Calculate overall risk score
        risk_score = self._calculate_risk_score(
            policy_assessment=policy_assessment,
            health_score=health_score,
            pattern_check=pattern_check,
            can_throttle=can_throttle,
            can_limit=can_limit,
        )
        
        # Determine if action should be allowed
        allowed = (
            policy_assessment.get("allowed", False)
            and can_throttle
            and can_limit
            and not pattern_check.get("has_abnormal_pattern", False)
            and health_score >= 0.3  # Minimum health threshold
        )
        
        return {
            "account_id": account_id,
            "action_type": action_type.value,
            "allowed": allowed,
            "risk_score": risk_score,
            "risk_level": self._score_to_risk_level(risk_score).value,
            "policy_assessment": policy_assessment,
            "throttling": {
                "allowed": can_throttle,
                "reason": throttle_reason,
            },
            "daily_limits": {
                "allowed": can_limit,
                "reason": limit_reason,
            },
            "pattern_check": pattern_check,
            "health": {
                "score": health_score,
                "status": health_status.value,
            },
            "recommendations": self._generate_recommendations(
                allowed=allowed,
                policy_assessment=policy_assessment,
                health_score=health_score,
                pattern_check=pattern_check,
            ),
        }
    
    def _calculate_risk_score(
        self,
        policy_assessment: Dict[str, Any],
        health_score: float,
        pattern_check: Dict[str, Any],
        can_throttle: bool,
        can_limit: bool,
    ) -> float:
        """Calculate overall risk score (0.0-1.0, higher = more risk)"""
        # Base risk from action type
        risk_level = policy_assessment.get("risk_level", "high")
        risk_mapping = {
            RiskLevel.VERY_LOW.value: 0.1,
            RiskLevel.LOW.value: 0.3,
            RiskLevel.MEDIUM.value: 0.5,
            RiskLevel.HIGH.value: 0.7,
            RiskLevel.VERY_HIGH.value: 0.9,
        }
        base_risk = risk_mapping.get(risk_level, 0.7)
        
        # Adjust based on health (lower health = higher risk)
        health_adjustment = (1.0 - health_score) * 0.3
        base_risk += health_adjustment
        
        # Adjust based on patterns
        if pattern_check.get("has_abnormal_pattern", False):
            base_risk += 0.2  # Significant penalty
        
        # Adjust based on throttling/limits
        if not can_throttle or not can_limit:
            base_risk += 0.1  # Approaching limits increases risk
        
        # Clamp to 0.0-1.0
        return max(0.0, min(1.0, base_risk))
    
    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level"""
        if score >= 0.8:
            return RiskLevel.VERY_HIGH
        elif score >= 0.6:
            return RiskLevel.HIGH
        elif score >= 0.4:
            return RiskLevel.MEDIUM
        elif score >= 0.2:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _generate_recommendations(
        self,
        allowed: bool,
        policy_assessment: Dict[str, Any],
        health_score: float,
        pattern_check: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations based on assessment"""
        recommendations = []
        
        if not allowed:
            recommendations.append("Action not allowed - review risk factors")
        
        if health_score < 0.5:
            recommendations.append(f"Account health is low ({health_score:.2f}) - consider pausing")
        
        if pattern_check.get("has_abnormal_pattern", False):
            recommendations.append("Abnormal patterns detected - reduce activity")
        
        if pattern_check.get("velocity_abnormal", False):
            recommendations.append("Action velocity is too high - slow down")
        
        if pattern_check.get("repetition_abnormal", False):
            recommendations.append("Repetitive actions detected - vary behavior")
        
        if not recommendations:
            recommendations.append("Proceed with normal caution")
        
        return recommendations
