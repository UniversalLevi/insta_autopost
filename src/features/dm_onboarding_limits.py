"""
Simple per-user/per-account limits for DM onboarding, similar to AI DM / DM tracking.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict

from src.utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("data")
LIMITS_FILE = DATA_DIR / "dm_onboarding_limits.json"


def _ensure_dir() -> None:
  DATA_DIR.mkdir(exist_ok=True, parents=True)


def _load() -> Dict[str, Any]:
  _ensure_dir()
  if not LIMITS_FILE.exists():
    return {}
  try:
    with open(LIMITS_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception as e:
    logger.warning("Failed to load DM onboarding limits", error=str(e))
    return {}


def _save(data: Dict[str, Any]) -> None:
  _ensure_dir()
  try:
    with open(LIMITS_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
  except Exception as e:
    logger.error("Failed to save DM onboarding limits", error=str(e))


def can_start_onboarding(account_id: str, user_id: str, max_per_day: int = 1) -> bool:
  """
  Check if this IG user can start onboarding flow again today.
  """
  data = _load()
  today = datetime.utcnow().date().isoformat()
  aid = str(account_id or "")
  uid = str(user_id or "")

  account_limits = data.get(aid) or {}
  day_entry = account_limits.get(today) or {}
  count = int(day_entry.get(uid) or 0)
  return count < max_per_day


def record_onboarding_start(account_id: str, user_id: str) -> None:
  """
  Record that an onboarding flow was started (or attempted) for this user today.
  """
  data = _load()
  today = datetime.utcnow().date().isoformat()
  aid = str(account_id or "")
  uid = str(user_id or "")

  if aid not in data:
    data[aid] = {}

  if today not in data[aid]:
    data[aid][today] = {}

  data[aid][today][uid] = int(data[aid][today].get(uid) or 0) + 1

  # Keep only last 7 days per account
  cutoff_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
  data[aid] = {
    day: user_counts
    for day, user_counts in data[aid].items()
    if day >= cutoff_date
  }

  _save(data)

