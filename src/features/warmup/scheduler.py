"""
Background scheduler for warm-up automation.
"""

import time
import threading
from datetime import datetime

from ...utils.logger import get_logger
from .store import load_plans, get_config
from .runner import run_one_cycle

logger = get_logger(__name__)

_stop = threading.Event()
_thread = None
_app_instance = None
_interval_seconds = 60 * 60


def _run_cycle():
    """Run automation for all accounts in active warm-up with automation enabled."""
    global _app_instance
    if not _app_instance:
        return
    app = _app_instance
    account_service = getattr(app, "account_service", None)
    browser_wrapper = getattr(app, "browser_wrapper", None)
    if not account_service or not browser_wrapper:
        return
    plans = load_plans()
    now = datetime.now()
    for plan in plans:
        if plan.status != "active":
            continue
        cfg = get_config(plan.account_id)
        if not cfg.automation_enabled:
            continue
        schedule_times = cfg.schedule_times or ["09:00", "14:00", "18:00"]
        schedule_hours = set()
        for st in schedule_times:
            try:
                parts = str(st).strip().split(":")
                if parts:
                    schedule_hours.add(int(parts[0]))
            except (ValueError, IndexError):
                pass
        if not schedule_hours:
            schedule_hours = {9, 14, 18}
        if now.hour not in schedule_hours:
            continue
        try:
            result = run_one_cycle(plan.account_id, account_service, browser_wrapper)
            if result.get("actions", 0) > 0:
                logger.info("Warm-up automation completed", account_id=plan.account_id, **result)
        except Exception as e:
            logger.exception("Warm-up automation failed", account_id=plan.account_id, error=str(e))


def _loop():
    """Main loop - run every hour."""
    logger.info("Warm-up automation scheduler started")
    while not _stop.is_set():
        try:
            _run_cycle()
        except Exception as e:
            logger.error("Warm-up automation cycle error", error=str(e))
        _stop.wait(_interval_seconds)
    logger.info("Warm-up automation scheduler stopped")


def start_scheduler(app) -> None:
    """Start the warm-up automation background thread."""
    global _thread, _app_instance
    if _thread is not None:
        logger.warning("Warm-up automation scheduler already running")
        return
    _app_instance = app
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="warmup-automation")
    _thread.start()
    logger.info("Warm-up automation scheduler started", interval_seconds=_interval_seconds)


def stop_scheduler() -> None:
    """Stop the warm-up automation scheduler."""
    global _thread
    _stop.set()
    if _thread:
        _thread.join(timeout=2)
        if _thread.is_alive():
            logger.warning("Warm-up automation thread still alive after timeout")
        _thread = None
    logger.info("Warm-up automation scheduler stopped")
