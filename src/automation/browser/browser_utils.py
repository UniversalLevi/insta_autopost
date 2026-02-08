"""Utility helpers for browser automation"""


class BrowserClosedError(Exception):
    """Raised when an operation failed because the browser was closed (e.g. during shutdown)."""


def is_browser_closed_error(exc: Exception) -> bool:
    """
    Detect errors that occur when the browser/page was closed during shutdown.
    These should be logged at debug level, not as login/automation failures.
    """
    msg = str(exc).lower()
    phrases = [
        "target page, context or browser has been closed",
        "connection closed while reading from the driver",
        "browser has been closed",
        "target closed",
        "browser closed",
        "page.goto: target",
        "page.goto: connection",
    ]
    return any(p in msg for p in phrases)
