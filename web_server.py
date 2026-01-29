"""Web server entry point for InstaForge web dashboard"""

import sys
import signal
import uvicorn
from pathlib import Path

# Add web directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file BEFORE importing anything else
from dotenv import load_dotenv
load_dotenv()

from web.main import app
from web.cloudflare_helper import start_cloudflare, stop_cloudflare

# Global Cloudflare cleanup handler
def cleanup_handler(signum, frame):
    """Handle shutdown signals"""
    from web.cloudinary_helper import is_cloudinary_configured
    # Only stop Cloudflare if it was started (i.e., Cloudinary not configured)
    if not is_cloudinary_configured():
        stop_cloudflare()
    sys.exit(0)


if __name__ == "__main__":
    # Get port from environment or use default
    import os
    port = int(os.getenv("WEB_PORT", 8000))
    host = os.getenv("WEB_HOST", "0.0.0.0")
    
    # Register signal handlers for cleanup
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
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
