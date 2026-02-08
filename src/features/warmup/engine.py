"""
Warm-up engine - start, pause, resume, complete day, mark task.
"""

from datetime import datetime
from typing import Dict, Any, Optional

from ...utils.logger import get_logger
from .store import get_plan, create_plan, update_plan, load_plans, save_warmup_report
from .plans import get_tasks_for_day

logger = get_logger(__name__)


def start_warmup(account_id: str, instagram_id: Optional[str] = None) -> Dict[str, Any]:
    """Start a new 5-day warm-up. Returns plan dict."""
    existing = get_plan(account_id)
    if existing and existing.status == "active":
        raise ValueError(f"Warm-up already active for account {account_id}")
    if existing and existing.status in ("completed", "paused"):
        from .store import remove_plan
        remove_plan(account_id)
    plan = create_plan(account_id, instagram_id)
    return plan.to_dict()


def get_today_plan(account_id: str) -> Optional[Dict[str, Any]]:
    """Get today's plan with task checklist. Returns dict or None."""
    plan = get_plan(account_id)
    if not plan or plan.status != "active":
        return None
    day = min(5, max(1, plan.current_day))
    tasks = get_tasks_for_day(day)
    completed = plan.completed_tasks or []

    task_list = []
    for t in tasks:
        tid = t.id
        done_count = sum(1 for c in completed if c.get("task_id") == tid)
        task_list.append({
            **t.to_dict(),
            "done_count": done_count,
            "completed": done_count >= t.target,
        })

    return {
        "account_id": account_id,
        "current_day": day,
        "status": plan.status,
        "start_date": plan.start_date,
        "risk_score": plan.risk_score,
        "tasks": task_list,
        "last_action_time": plan.last_action_time,
    }


def mark_task_done(account_id: str, task_id: str, count: int = 1) -> Optional[Dict[str, Any]]:
    """Mark a task as done. Returns updated plan dict or None."""
    plan = get_plan(account_id)
    if not plan or plan.status != "active":
        return None
    day = plan.current_day
    tasks = get_tasks_for_day(day)
    task_def = next((t for t in tasks if t.id == task_id), None)
    if not task_def:
        logger.warning("Unknown task", task_id=task_id, account_id=account_id)
        return None

    completed = list(plan.completed_tasks or [])
    for _ in range(count):
        completed.append({"task_id": task_id, "done_at": datetime.utcnow().isoformat()})

    updated = update_plan(account_id, {
        "completed_tasks": completed,
        "last_action_time": datetime.utcnow().isoformat(),
        "daily_actions_completed": {
            **(plan.daily_actions_completed or {}),
            f"day{day}": completed,
        },
    })
    return updated.to_dict() if updated else None


def complete_day(account_id: str) -> Optional[Dict[str, Any]]:
    """Mark current day complete and advance (or finish on Day 5)."""
    plan = get_plan(account_id)
    if not plan or plan.status != "active":
        return None
    day = plan.current_day
    if day >= 5:
        return _finish_warmup(account_id)
    updated = update_plan(account_id, {"current_day": day + 1})
    return updated.to_dict() if updated else None


def _finish_warmup(account_id: str) -> Optional[Dict[str, Any]]:
    """Mark warm-up as completed."""
    logger.info("Warm-up completed", account_id=account_id)
    return update_plan(account_id, {"status": "completed", "current_day": 5}).to_dict()


def pause_warmup(account_id: str, reason: str) -> Optional[Dict[str, Any]]:
    """Pause warm-up."""
    logger.warning("Warm-up paused", account_id=account_id, reason=reason)
    plan = get_plan(account_id)
    notes = (plan.notes if plan else "") + f"\nPaused: {reason}"
    updated = update_plan(account_id, {"status": "paused", "notes": notes})
    return updated.to_dict() if updated else None


def resume_warmup(account_id: str) -> Optional[Dict[str, Any]]:
    """Resume a paused warm-up."""
    updated = update_plan(account_id, {"status": "active"})
    return updated.to_dict() if updated else None
