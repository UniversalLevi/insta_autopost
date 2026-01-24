"""Policy engine for risk-based decision making"""

from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of actions that can be performed"""
    # API-based (Low-Medium Risk)
    POST_MEDIA = "post_media"
    POST_STORY = "post_story"
    COMMENT_API = "comment_api"
    DM_SEND_API = "dm_send_api"
    LIKE_API = "like_api"
    
    # Browser-based (High Risk)
    LIKE_BROWSER = "like_browser"
    COMMENT_BROWSER = "comment_browser"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"
    STORY_VIEW = "story_view"
    FEED_SCROLL = "feed_scroll"
    PROFILE_VIEW = "profile_view"
    DM_SEND_BROWSER = "dm_send_browser"
    SAVE = "save"
    SHARE = "share"


class RiskLevel(str, Enum):
    """Risk levels for actions"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ActionRiskProfile:
    """Risk profile for an action type"""
    
    def __init__(
        self,
        action_type: ActionType,
        risk_level: RiskLevel,
        min_cooldown_seconds: float,
        recommended_daily_limit: int,
        requires_warmup_days: int = 0,
        preferred_execution_method: str = "api",  # "api" or "browser"
    ):
        self.action_type = action_type
        self.risk_level = risk_level
        self.min_cooldown_seconds = min_cooldown_seconds
        self.recommended_daily_limit = recommended_daily_limit
        self.requires_warmup_days = requires_warmup_days
        self.preferred_execution_method = preferred_execution_method


class PolicyEngine:
    """
    Policy engine for risk-based decision making and action routing.
    
    Responsibilities:
    - Assess action risk levels
    - Determine if actions are allowed based on account state
    - Route actions to appropriate execution method (API vs Browser)
    - Apply safety policies and constraints
    """
    
    # Default risk profiles for action types
    ACTION_RISK_PROFILES = {
        ActionType.POST_MEDIA: ActionRiskProfile(
            action_type=ActionType.POST_MEDIA,
            risk_level=RiskLevel.LOW,
            min_cooldown_seconds=60,
            recommended_daily_limit=10,
            requires_warmup_days=0,
            preferred_execution_method="api",
        ),
        ActionType.LIKE_API: ActionRiskProfile(
            action_type=ActionType.LIKE_API,
            risk_level=RiskLevel.LOW,
            min_cooldown_seconds=5,
            recommended_daily_limit=100,
            requires_warmup_days=3,
            preferred_execution_method="api",
        ),
        ActionType.LIKE_BROWSER: ActionRiskProfile(
            action_type=ActionType.LIKE_BROWSER,
            risk_level=RiskLevel.HIGH,
            min_cooldown_seconds=10,
            recommended_daily_limit=80,
            requires_warmup_days=5,
            preferred_execution_method="browser",
        ),
        ActionType.COMMENT_API: ActionRiskProfile(
            action_type=ActionType.COMMENT_API,
            risk_level=RiskLevel.MEDIUM,
            min_cooldown_seconds=30,
            recommended_daily_limit=20,
            requires_warmup_days=5,
            preferred_execution_method="api",
        ),
        ActionType.COMMENT_BROWSER: ActionRiskProfile(
            action_type=ActionType.COMMENT_BROWSER,
            risk_level=RiskLevel.VERY_HIGH,
            min_cooldown_seconds=60,
            recommended_daily_limit=15,
            requires_warmup_days=6,
            preferred_execution_method="browser",
        ),
        ActionType.FOLLOW: ActionRiskProfile(
            action_type=ActionType.FOLLOW,
            risk_level=RiskLevel.VERY_HIGH,
            min_cooldown_seconds=60,
            recommended_daily_limit=50,
            requires_warmup_days=7,
            preferred_execution_method="browser",
        ),
        ActionType.UNFOLLOW: ActionRiskProfile(
            action_type=ActionType.UNFOLLOW,
            risk_level=RiskLevel.HIGH,
            min_cooldown_seconds=300,
            recommended_daily_limit=50,
            requires_warmup_days=7,
            preferred_execution_method="browser",
        ),
        ActionType.STORY_VIEW: ActionRiskProfile(
            action_type=ActionType.STORY_VIEW,
            risk_level=RiskLevel.MEDIUM,
            min_cooldown_seconds=5,
            recommended_daily_limit=100,
            requires_warmup_days=1,
            preferred_execution_method="browser",
        ),
        ActionType.DM_SEND_API: ActionRiskProfile(
            action_type=ActionType.DM_SEND_API,
            risk_level=RiskLevel.MEDIUM,
            min_cooldown_seconds=120,
            recommended_daily_limit=30,
            requires_warmup_days=5,
            preferred_execution_method="api",
        ),
        ActionType.DM_SEND_BROWSER: ActionRiskProfile(
            action_type=ActionType.DM_SEND_BROWSER,
            risk_level=RiskLevel.HIGH,
            min_cooldown_seconds=180,
            recommended_daily_limit=20,
            requires_warmup_days=6,
            preferred_execution_method="browser",
        ),
        ActionType.FEED_SCROLL: ActionRiskProfile(
            action_type=ActionType.FEED_SCROLL,
            risk_level=RiskLevel.VERY_LOW,
            min_cooldown_seconds=2,
            recommended_daily_limit=200,
            requires_warmup_days=1,
            preferred_execution_method="browser",
        ),
        ActionType.PROFILE_VIEW: ActionRiskProfile(
            action_type=ActionType.PROFILE_VIEW,
            risk_level=RiskLevel.VERY_LOW,
            min_cooldown_seconds=3,
            recommended_daily_limit=150,
            requires_warmup_days=1,
            preferred_execution_method="browser",
        ),
    }
    
    def __init__(self, custom_profiles: Optional[Dict[ActionType, ActionRiskProfile]] = None):
        """
        Initialize policy engine
        
        Args:
            custom_profiles: Custom risk profiles to override defaults
        """
        self.profiles = self.ACTION_RISK_PROFILES.copy()
        if custom_profiles:
            self.profiles.update(custom_profiles)
    
    def get_action_risk_profile(self, action_type: ActionType) -> Optional[ActionRiskProfile]:
        """Get risk profile for an action type"""
        return self.profiles.get(action_type)
    
    def assess_action_risk(
        self,
        action_type: ActionType,
        account_warmup_days: int = 0,
        account_health_score: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Assess risk of performing an action
        
        Args:
            action_type: Type of action to assess
            account_warmup_days: Days since account warm-up started
            account_health_score: Account health score (0.0-1.0)
            
        Returns:
            Risk assessment dictionary
        """
        profile = self.get_action_risk_profile(action_type)
        
        if not profile:
            return {
                "allowed": False,
                "reason": "unknown_action_type",
                "risk_level": RiskLevel.VERY_HIGH.value,
            }
        
        # Check warm-up requirements
        if account_warmup_days < profile.requires_warmup_days:
            return {
                "allowed": False,
                "reason": "insufficient_warmup",
                "required_warmup_days": profile.requires_warmup_days,
                "current_warmup_days": account_warmup_days,
                "risk_level": profile.risk_level.value,
            }
        
        # Adjust risk based on account health
        risk_multiplier = max(0.5, account_health_score)  # Lower health = higher effective risk
        
        # Check if action is allowed
        # For now, allow if warm-up requirement is met
        # Additional checks can be added (daily limits, cooldowns, etc.)
        allowed = True
        
        return {
            "allowed": allowed,
            "risk_level": profile.risk_level.value,
            "min_cooldown_seconds": profile.min_cooldown_seconds,
            "recommended_daily_limit": profile.recommended_daily_limit,
            "preferred_execution_method": profile.preferred_execution_method,
            "effective_risk": risk_multiplier,
        }
    
    def should_use_api(self, action_type: ActionType) -> bool:
        """
        Determine if action should use API or browser
        
        Args:
            action_type: Type of action
            
        Returns:
            True if API should be used, False for browser
        """
        profile = self.get_action_risk_profile(action_type)
        if not profile:
            return False  # Default to browser for unknown actions
        
        return profile.preferred_execution_method == "api"
    
    def get_recommended_cooldown(self, action_type: ActionType, account_health_score: float = 1.0) -> float:
        """
        Get recommended cooldown time for an action
        
        Args:
            action_type: Type of action
            account_health_score: Account health score (0.0-1.0)
            
        Returns:
            Recommended cooldown in seconds
        """
        profile = self.get_action_risk_profile(action_type)
        if not profile:
            return 300  # Default 5 minutes for unknown actions
        
        # Increase cooldown if account health is low
        health_multiplier = max(1.0, 2.0 - account_health_score)
        return profile.min_cooldown_seconds * health_multiplier
    
    def get_recommended_daily_limit(
        self,
        action_type: ActionType,
        account_warmup_days: int = 0,
        account_health_score: float = 1.0,
    ) -> int:
        """
        Get recommended daily limit for an action
        
        Args:
            action_type: Type of action
            account_warmup_days: Days since warm-up started
            account_health_score: Account health score
            
        Returns:
            Recommended daily limit
        """
        profile = self.get_action_risk_profile(action_type)
        if not profile:
            return 10  # Conservative default
        
        base_limit = profile.recommended_daily_limit
        
        # Adjust based on warm-up days (progressive increase)
        if account_warmup_days < profile.requires_warmup_days:
            return 0  # Not ready
        
        warmup_factor = min(1.0, account_warmup_days / 7.0)  # Ramp up over 7 days
        adjusted_limit = int(base_limit * warmup_factor)
        
        # Adjust based on health score
        health_factor = max(0.5, account_health_score)
        final_limit = int(adjusted_limit * health_factor)
        
        return max(1, final_limit)  # At least 1
