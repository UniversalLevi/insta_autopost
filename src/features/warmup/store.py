"""
Warm-up plans and config persistence.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from ...utils.logger import get_logger
from .models import WarmupPlan, WarmupConfig

logger = get_logger(__name__)

DATA_DIR = Path("data")
PLANS_FILE = DATA_DIR / "warmup_plans.json"
CONFIG_FILE = DATA_DIR / "warmup_automation_config.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True, parents=True)


# --- Plans ---

def _load_plans_raw() -> List[Dict[str, Any]]:
    _ensure_data_dir()
    if not PLANS_FILE.exists():
        return []
    try:
        with open(PLANS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        plans = data.get("plans", [])
        return plans if isinstance(plans, list) else []
    except Exception as e:
        logger.warning("Failed to load warmup plans", error=str(e))
        return []


def _save_plans_raw(plans: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(PLANS_FILE, "w", encoding="utf-8") as f:
        json.dump({"plans": plans, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)


def get_plan(account_id: str) -> Optional[WarmupPlan]:
    """Get warm-up plan for an account."""
    plans = _load_plans_raw()
    raw = next((p for p in plans if p.get("account_id") == account_id), None)
    return WarmupPlan.from_dict(raw) if raw else None


def remove_plan(account_id: str) -> None:
    """Remove a plan (e.g. to allow restart)."""
    plans = _load_plans_raw()
    plans = [p for p in plans if p.get("account_id") != account_id]
    _save_plans_raw(plans)


def create_plan(account_id: str, instagram_id: Optional[str] = None) -> WarmupPlan:
    """Create a new warm-up plan."""
    plans = _load_plans_raw()
    if any(p.get("account_id") == account_id for p in plans):
        raise ValueError(f"Warm-up plan already exists for account {account_id}")
    now = datetime.utcnow().isoformat()
    plan = WarmupPlan(
        account_id=account_id,
        instagram_id=instagram_id or account_id,
        start_date=now[:10],
        current_day=1,
        status="active",
        last_action_time=None,
        risk_score=0,
        daily_actions_completed={},
        completed_tasks=[],
        notes="",
        created_at=now,
        updated_at=now,
    )
    plans.append(plan.to_dict())
    _save_plans_raw(plans)
    logger.info("Warm-up plan created", account_id=account_id)
    return plan


def update_plan(account_id: str, updates: Dict[str, Any]) -> Optional[WarmupPlan]:
    """Update a warm-up plan. Returns updated plan or None."""
    plans = _load_plans_raw()
    for p in plans:
        if p.get("account_id") == account_id:
            p.update(updates)
            p["updated_at"] = datetime.utcnow().isoformat()
            _save_plans_raw(plans)
            return WarmupPlan.from_dict(p)
    return None


def load_plans() -> List[WarmupPlan]:
    """Load all warm-up plans."""
    raw = _load_plans_raw()
    return [WarmupPlan.from_dict(p) for p in raw]


# --- Config ---

def _load_config_raw() -> Dict[str, Dict[str, Any]]:
    _ensure_data_dir()
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        accounts = data.get("accounts", {})
        return accounts if isinstance(accounts, dict) else {}
    except Exception as e:
        logger.warning("Failed to load warmup automation config", error=str(e))
        return {}


def _save_config_raw(accounts: Dict[str, Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts}, f, indent=2)


def get_config(account_id: str) -> WarmupConfig:
    """Get automation config for an account."""
    accounts = _load_config_raw()
    raw = accounts.get(account_id, {})
    return WarmupConfig.from_dict(raw)


def set_config(account_id: str, updates: Dict[str, Any]) -> WarmupConfig:
    """Update automation config for an account."""
    accounts = _load_config_raw()
    cfg = accounts.get(account_id, get_config(account_id).to_dict())
    cfg.update(updates)
    accounts[account_id] = cfg
    _save_config_raw(accounts)
    return WarmupConfig.from_dict(cfg)


# --- Reports (for complete-day) ---

REPORTS_FILE = DATA_DIR / "warmup_reports.json"


def save_warmup_report(report: Dict[str, Any]) -> None:
    """Append a warm-up completion report."""
    _ensure_data_dir()
    reports = []
    if REPORTS_FILE.exists():
        try:
            with open(REPORTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            reports = data.get("reports", [])
        except Exception:
            pass
    reports.append(report)
    with open(REPORTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"reports": reports, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)
