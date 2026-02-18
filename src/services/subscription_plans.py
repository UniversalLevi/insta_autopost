"""Subscription plan definitions and limits. Payments disabled – all features available to everyone."""

from typing import Dict, Any

# Plan IDs (kept for user display; no payment enforcement)
PLAN_FREE = "free"
PLAN_STARTER = "starter"
PLAN_PRO = "pro"

# No payment integration – all plans have full access
PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    PLAN_FREE: {
        "name": "Free",
        "price": 0,
        "price_display": "Free",
        "accounts": 999,
        "scheduled_posts_per_month": -1,
        "ai_dm": True,
        "batch_upload": True,
        "batch_upload_max_files": 999,
        "warmup_automation": True,
        "comment_to_dm": True,
    },
    PLAN_STARTER: {
        "name": "Starter",
        "price": 0,
        "price_display": "Free",
        "accounts": 999,
        "scheduled_posts_per_month": -1,
        "ai_dm": True,
        "batch_upload": True,
        "batch_upload_max_files": 999,
        "warmup_automation": True,
        "comment_to_dm": True,
    },
    PLAN_PRO: {
        "name": "Pro",
        "price": 0,
        "price_display": "Free",
        "accounts": 999,
        "scheduled_posts_per_month": -1,
        "ai_dm": True,
        "batch_upload": True,
        "batch_upload_max_files": 999,
        "warmup_automation": True,
        "comment_to_dm": True,
    },
}


def get_plan_limits(plan: str) -> Dict[str, Any]:
    """Return limits for a plan. All plans have full access."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[PLAN_FREE]).copy()


def can_use_feature(plan: str, feature: str, current_count: int = 0) -> bool:
    """Check if user's plan allows a feature. Always True – payments disabled."""
    limits = get_plan_limits(plan)
    if feature == "accounts":
        return current_count < limits["accounts"]
    if feature == "scheduled_posts":
        if limits["scheduled_posts_per_month"] == -1:
            return True
        return current_count < limits["scheduled_posts_per_month"]
    if feature == "ai_dm":
        return limits["ai_dm"]
    if feature == "batch_upload":
        return limits["batch_upload"]
    if feature == "batch_upload_files":
        return current_count <= limits["batch_upload_max_files"]
    if feature == "warmup_automation":
        return limits["warmup_automation"]
    if feature == "comment_to_dm":
        return limits["comment_to_dm"]
    return True
