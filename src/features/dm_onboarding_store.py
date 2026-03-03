"""
DM Onboarding Store - Tracks simple, per-user onboarding state for the
Instagram → EazyDS store creation flow.

Pattern is similar to other JSON-backed stores in this project.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("data")
STATE_FILE = DATA_DIR / "dm_onboarding.json"
RETENTION_DAYS = 30


def _ensure_dir() -> None:
  DATA_DIR.mkdir(exist_ok=True, parents=True)


def _load() -> Dict[str, Any]:
  _ensure_dir()
  if not STATE_FILE.exists():
    return {"sessions": {}}
  try:
    with open(STATE_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception as e:
    logger.warning("Failed to load DM onboarding store", error=str(e))
    return {"sessions": {}}


def _save(data: Dict[str, Any]) -> None:
  _ensure_dir()
  try:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
  except Exception as e:
    logger.error("Failed to save DM onboarding store", error=str(e))


def _session_key(account_id: str, user_id: str) -> str:
  return f"{account_id}:{user_id}"


def get_session(account_id: str, user_id: str) -> Dict[str, Any]:
  """
  Get or initialize a DM onboarding session for a given account + IG user.
  """
  data = _load()
  sessions = data.get("sessions") or {}
  key = _session_key(str(account_id or ""), str(user_id or ""))
  now_iso = datetime.utcnow().isoformat()

  if key not in sessions:
    sessions[key] = {
      "account_id": str(account_id or ""),
      "user_id": str(user_id or ""),
      "step": "idle",
      "data": {},
      "attemptCount": 0,
      "createdAt": now_iso,
      "updatedAt": now_iso,
      "hasCreatedStore": False,
    }
    data["sessions"] = sessions
    _save(data)

  return sessions[key]


def update_session(account_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
  """
  Merge updates into a session and persist it.
  """
  data = _load()
  sessions = data.get("sessions") or {}
  key = _session_key(str(account_id or ""), str(user_id or ""))
  now_iso = datetime.utcnow().isoformat()

  if key not in sessions:
    sessions[key] = {
      "account_id": str(account_id or ""),
      "user_id": str(user_id or ""),
      "step": "idle",
      "data": {},
      "attemptCount": 0,
      "createdAt": now_iso,
      "updatedAt": now_iso,
      "hasCreatedStore": False,
    }

  session = sessions[key]

  # Shallow merge
  for k, v in updates.items():
    if k == "data" and isinstance(v, dict):
      existing = session.get("data") or {}
      existing.update(v)
      session["data"] = existing
    else:
      session[k] = v

  session["updatedAt"] = now_iso
  sessions[key] = session
  data["sessions"] = sessions

  # Cleanup old sessions
  cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
  cutoff_iso = cutoff.isoformat()
  data["sessions"] = {
    k: v for k, v in data["sessions"].items()
    if (v.get("updatedAt") or v.get("createdAt") or "") >= cutoff_iso
  }

  _save(data)
  return session


def reset_session(account_id: str, user_id: str) -> None:
  """
  Remove a session entirely (e.g., after completion or hard failure).
  """
  data = _load()
  sessions = data.get("sessions") or {}
  key = _session_key(str(account_id or ""), str(user_id or ""))
  if key in sessions:
    sessions.pop(key, None)
    data["sessions"] = sessions
    _save(data)

