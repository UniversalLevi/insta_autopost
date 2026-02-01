"""Web server entry point for InstaForge web dashboard"""

import sys
import signal
import socket
import uvicorn
from pathlib import Path

# Add web directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file BEFORE importing anything else
from dotenv import load_dotenv
load_dotenv()

# Signal to web.main that we start Cloudflare here; avoid starting it again in startup_event
import os
os.environ.setdefault("CLOUDFLARE_STARTED_BY_WEB_SERVER", "1")

from web.main import app
from web.cloudflare_helper import start_cloudflare, stop_cloudflare


def _port_in_use(host: str, port: int) -> bool:
    """Return True if the given port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _get_available_port(host: str, preferred: int, max_tries: int = 10) -> int:
    """Return preferred port if free, otherwise the first free port in [preferred, preferred+max_tries)."""
    for p in range(preferred, preferred + max_tries):
        if not _port_in_use(host, p):
            return p
    raise RuntimeError(
        f"None of the ports {preferred}-{preferred + max_tries - 1} are available. "
        "Stop the process using the port or set WEB_PORT to a different number."
    )


# Global Cloudflare cleanup handler (SIGTERM only; SIGINT is ignored so Ctrl+C doesn't stop the server)
def cleanup_handler(signum, frame):
    """Handle shutdown signals (SIGTERM). Stops Cloudflare and exits."""
    from web.cloudinary_helper import is_cloudinary_configured
    if not is_cloudinary_configured():
        stop_cloudflare()
    sys.exit(0)


if __name__ == "__main__":
    # Get port from environment or use default; resolve to an available port if in use
    host = os.getenv("WEB_HOST", "0.0.0.0")
    preferred_port = int(os.getenv("WEB_PORT", "8000"))
    port = _get_available_port(host, preferred_port)
    if port != preferred_port:
        print(f"Port {preferred_port} is in use; using port {port} instead.")

    # Ignore Ctrl+C (SIGINT) so the server is not closed by accidental keypress.
    # To stop the server: close the terminal, or send SIGTERM (e.g. taskkill /PID <pid> on Windows).
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
    print(f"Starting InstaForge Web Dashboard...")
    print(f"Local server will be available at: http://localhost:{port}")
    print("Ctrl+C is ignored; to stop the server, close the terminal or use Task Manager.")
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

    try:
        # Use 1 worker by default; set WEB_WORKERS=2+ for more concurrency (not recommended on Windows with Cloudflare tunnel)
        workers = int(os.getenv("WEB_WORKERS", "1"))
        uvicorn.run(
            app,
            host=host,
            port=port,
            workers=workers,
            reload=False,  # Set to True for development
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Only stop Cloudflare if it was started (i.e., Cloudinary not configured)
        from web.cloudinary_helper import is_cloudinary_configured
        if not is_cloudinary_configured():
            stop_cloudflare()
