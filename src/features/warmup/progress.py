"""
In-memory progress store for warm-up automation runs.
Allows the UI to poll and display real-time progress.
"""

import threading
from typing import Dict, Any, Optional

_progress: Dict[str, Dict[str, Any]] = {}
_stop_requested: Dict[str, bool] = {}
_lock = threading.Lock()


def request_stop(account_id: str) -> None:
    """Request that the current warm-up run for this account stops."""
    with _lock:
        _stop_requested[account_id] = True


def is_stop_requested(account_id: str) -> bool:
    """Check if stop was requested for this account's run."""
    with _lock:
        return _stop_requested.get(account_id, False)


def clear_stop_request(account_id: str) -> None:
    """Clear stop request (call at start of run)."""
    with _lock:
        _stop_requested.pop(account_id, None)


def set_progress(
    account_id: str,
    phase: str,
    message: str,
    actions: int = 0,
    errors: int = 0,
    tasks_done: Optional[list] = None,
) -> None:
    """Update progress for an account's current run."""
    with _lock:
        _progress[account_id] = {
            "account_id": account_id,
            "phase": phase,
            "message": message,
            "actions": actions,
            "errors": errors,
            "tasks_done": tasks_done or [],
            "running": phase != "done" and phase != "error",
        }


def get_progress(account_id: str) -> Optional[Dict[str, Any]]:
    """Get current progress for an account."""
    with _lock:
        return _progress.get(account_id)


def clear_progress(account_id: str) -> None:
    """Clear progress after run completes (optional, for cleanup)."""
    with _lock:
        _progress.pop(account_id, None)
