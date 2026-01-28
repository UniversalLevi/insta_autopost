"""Background scheduler for warming actions that runs schedule.run_pending() in a loop."""

import time
import threading
import schedule
from src.utils.logger import get_logger

logger = get_logger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None
_app_instance = None


def _scheduler_loop():
    """Run schedule.run_pending() in a loop"""
    global _app_instance
    logger.info("Warming scheduler loop started")
    
    while not _stop.is_set():
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error("Error in warming scheduler loop", error=str(e))
        # Check every minute for scheduled tasks
        _stop.wait(60)
    
    logger.info("Warming scheduler loop stopped")


def start_warming_scheduler(app) -> None:
    """Start the warming scheduler background thread"""
    global _thread, _app_instance
    
    if _thread is not None:
        logger.warning("Warming scheduler already running")
        return
    
    _app_instance = app
    
    # Schedule warming actions
    try:
        app.schedule_warming()
        logger.info("Warming actions scheduled successfully")
    except Exception as e:
        logger.error("Failed to schedule warming actions", error=str(e))
        return
    
    # Start background thread to run scheduler
    _stop.clear()
    _thread = threading.Thread(
        target=_scheduler_loop,
        daemon=True,
        name="warming-scheduler",
    )
    _thread.start()
    logger.info("Warming scheduler background thread started")


def stop_warming_scheduler() -> None:
    """Stop the warming scheduler"""
    global _thread
    
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)
        _thread = None
    
    # Clear all scheduled jobs
    schedule.clear()
    logger.info("Warming scheduler stopped and cleared")
