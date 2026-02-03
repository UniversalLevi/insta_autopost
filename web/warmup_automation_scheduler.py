"""Background scheduler for warm-up automation - runs like/comment/save for accounts in warm-up."""

import time
import threading
from datetime import datetime

from src.utils.logger import get_logger
from src.features.warmup.warmup_store import load_warmup_plans
from src.features.warmup.warmup_automation_config import get_config

logger = get_logger(__name__)

_stop = threading.Event()
_thread = None
_app_instance = None
_interval_seconds = 60 * 60  # Check every hour


def _run_warmup_automation():
    """Run automation for all accounts in active warm-up with automation enabled."""
    global _app_instance
    if not _app_instance:
        return
    app = _app_instance
    account_service = getattr(app, "account_service", None)
    browser_wrapper = getattr(app, "browser_wrapper", None)
    if not account_service or not browser_wrapper:
        return
    from src.features.warmup.warmup_automation import WarmupAutomation
    automation = WarmupAutomation(account_service, browser_wrapper)
    plans = load_warmup_plans()
    now = datetime.now()
    for plan in plans:
        if plan.get("status") != "active":
            continue
        account_id = plan.get("account_id")
        cfg = get_config(account_id)
        if not cfg.get("automation_enabled"):
            continue
        schedule_times = cfg.get("schedule_times") or ["09:00", "14:00", "18:00"]
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
            result = automation.run_for_account(account_id)
            if result.get("actions", 0) > 0:
                logger.info("Warmup automation completed", account_id=account_id, **result)
        except Exception as e:
            logger.exception("Warmup automation failed", account_id=account_id, error=str(e))


def _loop():
    """Main loop - run every hour, or at scheduled times."""
    logger.info("Warmup automation scheduler started")
    while not _stop.is_set():
        try:
            _run_warmup_automation()
        except Exception as e:
            logger.error("Warmup automation cycle error", error=str(e))
        _stop.wait(_interval_seconds)
    logger.info("Warmup automation scheduler stopped")


def start_warmup_automation_scheduler(app) -> None:
    """Start the warm-up automation background thread."""
    global _thread, _app_instance
    if _thread is not None:
        logger.warning("Warmup automation scheduler already running")
        return
    _app_instance = app
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="warmup-automation")
    _thread.start()
    logger.info("Warmup automation scheduler started", interval_seconds=_interval_seconds)


def stop_warmup_automation_scheduler() -> None:
    """Stop the warm-up automation scheduler."""
    global _thread
    _stop.set()
    if _thread:
        _thread.join(timeout=2)
        if _thread.is_alive():
            logger.warning("Warmup automation thread still alive after timeout")
        _thread = None
    logger.info("Warmup automation scheduler stopped")
