"""
Warm-Up Plans Storage - Phase 1 Data Model
Stores warmup state per account in data/warmup_plans.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from ...utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("data")
WARMUP_PLANS_FILE = DATA_DIR / "warmup_plans.json"
WARMUP_REPORTS_FILE = DATA_DIR / "warmup_reports.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True, parents=True)


def load_warmup_plans() -> List[Dict[str, Any]]:
    """Load all warmup plans from disk."""
    _ensure_data_dir()
    if not WARMUP_PLANS_FILE.exists():
        return []
    try:
        with open(WARMUP_PLANS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("plans", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception as e:
        logger.warning("Failed to load warmup plans", error=str(e))
        return []


def save_warmup_plans(plans: List[Dict[str, Any]]) -> None:
    """Save warmup plans to disk."""
    _ensure_data_dir()
    with open(WARMUP_PLANS_FILE, "w", encoding="utf-8") as f:
        json.dump({"plans": plans, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)


def get_warmup_plan(account_id: str) -> Optional[Dict[str, Any]]:
    """Get warmup plan for an account by account_id."""
    plans = load_warmup_plans()
    return next((p for p in plans if p.get("account_id") == account_id), None)


def create_warmup_plan(
    account_id: str,
    instagram_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new warmup plan. Returns the created plan."""
    plans = load_warmup_plans()
    if any(p.get("account_id") == account_id for p in plans):
        raise ValueError(f"Warmup plan already exists for account {account_id}")
    now = datetime.utcnow().isoformat()
    plan = {
        "account_id": account_id,
        "instagram_id": instagram_id or account_id,
        "start_date": now[:10],
        "current_day": 1,
        "status": "active",
        "last_action_time": None,
        "risk_score": 0,
        "daily_actions_completed": {},
        "completed_tasks": [],
        "notes": "",
        "created_at": now,
        "updated_at": now,
    }
    plans.append(plan)
    save_warmup_plans(plans)
    logger.info("Warmup plan created", account_id=account_id)
    return plan


def update_warmup_plan(account_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update warmup plan. Returns updated plan or None if not found."""
    plans = load_warmup_plans()
    for p in plans:
        if p.get("account_id") == account_id:
            p.update(updates)
            p["updated_at"] = datetime.utcnow().isoformat()
            save_warmup_plans(plans)
            return p
    return None


def load_warmup_reports() -> List[Dict[str, Any]]:
    """Load warmup reports from disk."""
    _ensure_data_dir()
    if not WARMUP_REPORTS_FILE.exists():
        return []
    try:
        with open(WARMUP_REPORTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("reports", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception as e:
        logger.warning("Failed to load warmup reports", error=str(e))
        return []


def save_warmup_report(report: Dict[str, Any]) -> None:
    """Append a warmup report."""
    _ensure_data_dir()
    reports = load_warmup_reports()
    reports.append(report)
    with open(WARMUP_REPORTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"reports": reports, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)
