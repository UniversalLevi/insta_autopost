"""
Warmup Engine - Phase 2 & 3
Calculates day, generates daily tasks, enforces limits, updates progress.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ...utils.logger import get_logger
from .warmup_store import get_warmup_plan, update_warmup_plan, create_warmup_plan, load_warmup_plans
from .day_plans import WARMUP_DAY_PLANS

logger = get_logger(__name__)


class WarmupEngine:
    """Engine for 5-day Instagram account warm-up."""

    def __init__(self):
        pass

    def start_warmup(self, account_id: str, instagram_id: Optional[str] = None) -> Dict[str, Any]:
        """Start a new 5-day warm-up for an account."""
        existing = get_warmup_plan(account_id)
        if existing and existing.get("status") == "active":
            raise ValueError(f"Warm-up already active for account {account_id}")
        if existing and existing.get("status") in ("completed", "paused"):
            # Allow restart by creating fresh plan
            plans = load_warmup_plans()
            plans = [p for p in plans if p.get("account_id") != account_id]
            from .warmup_store import save_warmup_plans
            save_warmup_plans(plans)
        return create_warmup_plan(account_id=account_id, instagram_id=instagram_id)

    def get_today_plan(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get today's warm-up plan with task checklist for the account."""
        plan = get_warmup_plan(account_id)
        if not plan or plan.get("status") != "active":
            return None
        day = min(5, max(1, plan.get("current_day", 1)))
        tasks = WARMUP_DAY_PLANS.get(day, [])
        completed = plan.get("completed_tasks", []) or []
        daily_key = f"day{day}"
        daily_done = plan.get("daily_actions_completed", {}).get(daily_key, [])

        task_list = []
        for t in tasks:
            tid = t.get("id", "")
            done_count = sum(1 for c in completed if c.get("task_id") == tid)
            task_list.append({
                **t,
                "done_count": done_count,
                "completed": done_count >= t.get("target", 1),
            })

        return {
            "account_id": account_id,
            "current_day": day,
            "status": plan.get("status"),
            "start_date": plan.get("start_date"),
            "risk_score": plan.get("risk_score", 0),
            "tasks": task_list,
            "last_action_time": plan.get("last_action_time"),
        }

    def mark_task_done(
        self,
        account_id: str,
        task_id: str,
        count: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """Mark a task as done. Returns updated plan."""
        plan = get_warmup_plan(account_id)
        if not plan or plan.get("status") != "active":
            return None
        day = plan.get("current_day", 1)
        tasks = WARMUP_DAY_PLANS.get(day, [])
        task_def = next((t for t in tasks if t.get("id") == task_id), None)
        if not task_def:
            logger.warning("Unknown task", task_id=task_id, account_id=account_id)
            return None

        completed = plan.get("completed_tasks", []) or []
        for _ in range(count):
            completed.append({
                "task_id": task_id,
                "done_at": datetime.utcnow().isoformat(),
            })
        return update_warmup_plan(account_id, {
            "completed_tasks": completed,
            "last_action_time": datetime.utcnow().isoformat(),
            "daily_actions_completed": {
                **(plan.get("daily_actions_completed") or {}),
                f"day{day}": completed,
            },
        })

    def complete_day(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Mark current day complete and advance to next day (or finish)."""
        plan = get_warmup_plan(account_id)
        if not plan or plan.get("status") != "active":
            return None
        day = plan.get("current_day", 1)
        if day >= 5:
            return self.finish_warmup(account_id)
        return update_warmup_plan(account_id, {"current_day": day + 1})

    def pause_warmup(self, account_id: str, reason: str) -> Optional[Dict[str, Any]]:
        """Pause warm-up (e.g. on risk detected)."""
        logger.warning("Warm-up paused", account_id=account_id, reason=reason)
        return update_warmup_plan(account_id, {
            "status": "paused",
            "notes": (get_warmup_plan(account_id) or {}).get("notes", "") + f"\nPaused: {reason}",
        })

    def finish_warmup(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Mark warm-up as completed."""
        logger.info("Warm-up completed", account_id=account_id)
        return update_warmup_plan(account_id, {"status": "completed", "current_day": 5})

    def resume_warmup(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Resume a paused warm-up."""
        return update_warmup_plan(account_id, {"status": "active"})
