"""
Warmup Guard - Phase 6
Middleware: when warm-up is active, apply limits and block unsafe automation.
Bulk posting, mass DM, campaigns, broadcasts → disabled.
Guided actions and safe API calls → allowed with limits.
"""

from typing import Optional

from src.features.warmup.store import get_plan


def is_warmup_active(account_id: str) -> bool:
    """Return True if account has an active warm-up in progress."""
    plan = get_plan(account_id)
    return plan is not None and plan.status == "active"


def warmup_allows_action(
    account_id: str,
    action_type: str,
) -> tuple[bool, Optional[str]]:
    """
    Check if an action is allowed during warm-up.
    action_type: 'bulk_post' | 'mass_dm' | 'campaign' | 'broadcast' | 'guided' | 'safe_api'
    Returns (allowed, reason_if_blocked).
    """
    if not is_warmup_active(account_id):
        return True, None

    blocked = {"bulk_post", "mass_dm", "campaign", "broadcast"}
    if action_type in blocked:
        return False, f"Account is in warm-up: {action_type} is disabled"

    return True, None
