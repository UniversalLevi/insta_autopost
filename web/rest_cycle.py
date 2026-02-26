"""
Rest cycle: after the server has been running for X hours, pause all background
automation for Y minutes (rest), then resume. The web server stays up; only
automation (scheduled posts, warming, comment monitor, etc.) rests.
Helps avoid 24/7 automation patterns while keeping the site available.
"""

import os
import time
import threading
from src.utils.logger import get_logger

logger = get_logger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None
_cycle_start_time: float = 0.0
_rest_minutes: int = 15
_uptime_hours: float = 6.0
_check_interval_seconds: int = 5 * 60  # check every 5 minutes


def _stop_automation(app) -> None:
    """Stop all background automation (same as shutdown, but process keeps running)."""
    from .scheduled_publisher import stop_scheduled_publisher
    from .warming_scheduler import stop_warming_scheduler
    from src.features.warmup.scheduler import stop_scheduler as stop_warmup_automation_scheduler
    from src.services.token_refresher import stop_daily_token_refresh_job

    try:
        if getattr(app, "comment_monitor", None):
            app.comment_monitor.stop_monitoring_all_accounts()
    except Exception as e:
        logger.warning("Rest cycle: error stopping comment monitor", error=str(e))
    try:
        stop_scheduled_publisher()
    except Exception as e:
        logger.warning("Rest cycle: error stopping scheduled publisher", error=str(e))
    try:
        stop_daily_token_refresh_job()
    except Exception as e:
        logger.warning("Rest cycle: error stopping token refresher", error=str(e))
    try:
        stop_warming_scheduler()
    except Exception as e:
        logger.warning("Rest cycle: error stopping warming scheduler", error=str(e))
    try:
        stop_warmup_automation_scheduler()
    except Exception as e:
        logger.warning("Rest cycle: error stopping warmup automation scheduler", error=str(e))
    try:
        if getattr(app, "account_health_service", None):
            app.account_health_service.stop_monitoring()
    except Exception as e:
        logger.warning("Rest cycle: error stopping health monitoring", error=str(e))


def _start_automation(app) -> None:
    """Start all background automation again (same as startup when not in sleep mode)."""
    from .scheduled_publisher import start_scheduled_publisher
    from .warming_scheduler import start_warming_scheduler
    from src.features.warmup.scheduler import start_scheduler as start_warmup_automation_scheduler
    from src.services.token_refresher import start_daily_token_refresh_job
    from .cron_config import SCHEDULED_PUBLISHER_INTERVAL_SECONDS, TOKEN_REFRESH_INTERVAL_SECONDS

    try:
        if getattr(app, "comment_monitor", None):
            app.comment_monitor.start_monitoring_all_accounts()
    except Exception as e:
        logger.error("Rest cycle: error starting comment monitor", error=str(e), exc_info=True)
    try:
        start_scheduled_publisher(app, interval_seconds=SCHEDULED_PUBLISHER_INTERVAL_SECONDS)
    except Exception as e:
        logger.error("Rest cycle: error starting scheduled publisher", error=str(e), exc_info=True)
    try:
        start_daily_token_refresh_job(app, interval_seconds=TOKEN_REFRESH_INTERVAL_SECONDS)
    except Exception as e:
        logger.error("Rest cycle: error starting token refresher", error=str(e), exc_info=True)
    try:
        start_warming_scheduler(app)
    except Exception as e:
        logger.error("Rest cycle: error starting warming scheduler", error=str(e), exc_info=True)
    try:
        start_warmup_automation_scheduler(app)
    except Exception as e:
        logger.error("Rest cycle: error starting warmup automation scheduler", error=str(e), exc_info=True)
    try:
        if getattr(app, "account_health_service", None):
            app.account_health_service.start_monitoring()
    except Exception as e:
        logger.error("Rest cycle: error starting health monitoring", error=str(e), exc_info=True)


def _loop(app) -> None:
    """Background loop: every check interval, see if we should enter rest, then rest and resume."""
    global _cycle_start_time
    _cycle_start_time = time.time()
    logger.info(
        "Rest cycle started",
        uptime_hours=_uptime_hours,
        rest_minutes=_rest_minutes,
        check_interval_seconds=_check_interval_seconds,
    )
    while not _stop.is_set():
        try:
            _stop.wait(_check_interval_seconds)
        except Exception as e:
            logger.warning("Rest cycle wait error", error=str(e))
            time.sleep(min(300, _check_interval_seconds))
        if _stop.is_set():
            break
        try:
            uptime_seconds = time.time() - _cycle_start_time
            uptime_hours = uptime_seconds / 3600.0
            if uptime_hours < _uptime_hours:
                continue
            # Time to rest: pause automation for rest_minutes, then resume
            logger.info(
                "Rest cycle: pausing automation for rest",
                rest_minutes=_rest_minutes,
                uptime_hours=round(uptime_hours, 1),
            )
            _stop_automation(app)
            # Sleep for rest period (wake every 30s to check _stop so we can exit cleanly)
            slept = 0
            while slept < _rest_minutes * 60 and not _stop.is_set():
                try:
                    _stop.wait(min(30, _rest_minutes * 60 - slept))
                except Exception as e:
                    logger.warning("Rest cycle rest-wait error", error=str(e))
                slept += 30
            if _stop.is_set():
                break
            logger.info("Rest cycle: resuming automation")
            _start_automation(app)
            _cycle_start_time = time.time()
        except Exception as e:
            logger.exception("Rest cycle loop error", error=str(e))
    logger.info("Rest cycle loop stopped")


def start_rest_cycle(app) -> None:
    """Start the rest-cycle background thread. Idempotent."""
    global _thread, _rest_minutes, _uptime_hours, _check_interval_seconds
    if _thread is not None:
        logger.warning("Rest cycle already running")
        return
    enabled = (os.getenv("REST_CYCLE_ENABLED") or "").strip().lower() in ("1", "true", "yes")
    if not enabled:
        return
    try:
        _uptime_hours = float(os.getenv("REST_CYCLE_UPTIME_HOURS", "6").strip() or "6")
    except (ValueError, TypeError):
        _uptime_hours = 6.0
    try:
        _rest_minutes = int(os.getenv("REST_CYCLE_REST_MINUTES", "15").strip() or "15")
    except (ValueError, TypeError):
        _rest_minutes = 15
    try:
        _check_interval_seconds = int(os.getenv("REST_CYCLE_CHECK_MINUTES", "5").strip() or "5") * 60
    except (ValueError, TypeError):
        _check_interval_seconds = 5 * 60
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(app,), daemon=True, name="rest-cycle")
    _thread.start()
    print(
        f"Rest cycle enabled: automation will pause for {_rest_minutes} min after every {_uptime_hours} hours, then resume."
    )
    logger.info(
        "Rest cycle started",
        uptime_hours=_uptime_hours,
        rest_minutes=_rest_minutes,
    )


def stop_rest_cycle() -> None:
    """Stop the rest-cycle background thread."""
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=10)
        if _thread.is_alive():
            logger.warning("Rest cycle thread still alive after timeout")
        _thread = None
    logger.info("Rest cycle stopped")
