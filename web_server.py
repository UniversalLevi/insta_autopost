"""Web server entry point for InstaForge web dashboard"""

import sys
import signal
import uvicorn
from pathlib import Path

# Add web directory to path
sys.path.insert(0, str(Path(__file__).parent))

from web.main import app
from web.cloudflare_helper import start_cloudflare, stop_cloudflare

# Global Cloudflare cleanup handler
def cleanup_handler(signum, frame):
    """Handle shutdown signals"""
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
    print(f"Default password: {os.getenv('WEB_PASSWORD', 'admin')}")
    print(f"\nSet WEB_PASSWORD environment variable to change the password.\n")
    
    # Start Cloudflare tunnel automatically
    cloudflare_url = start_cloudflare(port)
    
    if cloudflare_url:
        print(f"✓ Using Cloudflare HTTPS URL for media uploads: {cloudflare_url}")
        print(f"  Instagram will be able to access uploaded files via this URL.\n")
    else:
        print(f"⚠ Warning: Cloudflare tunnel not available. Uploaded files will use localhost URLs.")
        print(f"  Instagram cannot access localhost URLs - install cloudflared or use cloud storage.\n")
    
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
        stop_cloudflare()
