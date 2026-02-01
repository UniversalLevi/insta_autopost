"""Web server entry point for InstaForge web dashboard"""

import asyncio
import logging
import sys
import uvicorn
from pathlib import Path

# Add web directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file BEFORE importing anything else
from dotenv import load_dotenv
load_dotenv()

from web.main import app
from web.cloudflare_helper import start_cloudflare, stop_cloudflare


class ShutdownExceptionFilter(logging.Filter):
    """Suppress ERROR tracebacks for CancelledError/KeyboardInterrupt during CTRL+C shutdown."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.ERROR:
            return True
        exc_type, exc_val, _ = (record.exc_info or (None, None, None))[:3]
        if exc_type is not None and exc_val is not None:
            if isinstance(exc_val, (asyncio.CancelledError, KeyboardInterrupt)):
                return False
        msg = (record.getMessage() or "")
        if "CancelledError" in msg or "KeyboardInterrupt" in msg:
            return False
        return True


def _install_shutdown_log_filter():
    """Install filter so CTRL+C doesn't flood the console with expected shutdown errors."""
    f = ShutdownExceptionFilter()
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.asgi",
        "uvicorn.protocols.http.httptools_impl",
        "starlette",
    ):
        logging.getLogger(name).addFilter(f)


# No custom signal handlers: let uvicorn handle SIGINT/SIGTERM for graceful shutdown.
# FastAPI shutdown_event (web/main.py) and the finally block below handle Cloudflare cleanup.


if __name__ == "__main__":
    # Get port from environment or use default
    import os
    port = int(os.getenv("WEB_PORT", 8000))
    host = os.getenv("WEB_HOST", "0.0.0.0")
    
    print(f"Starting InstaForge Web Dashboard...")
    print(f"Local server will be available at: http://localhost:{port}")
    if os.getenv("WEB_PASSWORD"):
        print("Web login: use your configured WEB_PASSWORD.")
    else:
        print("Web login: default user 'admin' / set WEB_PASSWORD to change from default.")
    print()

    # Uploads: use your server (BASE_URL) — no Cloudflare/Cloudinary messages unless needed
    base_url = (os.getenv("BASE_URL") or os.getenv("APP_URL") or "").strip().rstrip("/")
    if base_url:
        print(f"Uploads: served from your server ({base_url}).")
        cloudflare_url = None
    else:
        from web.cloudinary_helper import is_cloudinary_configured
        if is_cloudinary_configured():
            cloudflare_url = None
        else:
            cloudflare_url = start_cloudflare(port)
        # No Cloudflare/Cloudinary warning messages — upload from disk goes to server; set BASE_URL in production
    print()

    _install_shutdown_log_filter()

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,  # Set to True for development
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Only stop Cloudflare if it was started (i.e., Cloudinary not configured)
        from web.cloudinary_helper import is_cloudinary_configured
        if not is_cloudinary_configured():
            stop_cloudflare()
