"""FastAPI main application for InstaForge web dashboard"""

import sys
from pathlib import Path
from typing import Optional

import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, PlainTextResponse
from jinja2 import Environment, FileSystemLoader

from .api import router as api_router, auth_router
from .cloudflare_helper import start_cloudflare, stop_cloudflare, get_cloudflare_url
from .instagram_webhook import process_webhook_payload
from .scheduled_publisher import start_scheduled_publisher, stop_scheduled_publisher
from src.app import InstaForgeApp
from src.services.token_refresher import start_daily_token_refresh_job, stop_daily_token_refresh_job

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize FastAPI app
app = FastAPI(
    title="InstaForge Web Dashboard",
    description="Web dashboard for Instagram automation",
    version="1.0.0",
)

# CORS middleware - configurable for production
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if ENVIRONMENT == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Uploads directory (create if it doesn't exist)
uploads_path = Path("uploads")
uploads_path.mkdir(exist_ok=True)

# Direct file serving route for uploads (for better Instagram compatibility)
# IMPORTANT: This route MUST be public (no auth) and serve raw bytes with correct Content-Type
# Instagram's crawler requires clean access without cookies, auth, or redirects
@app.options("/uploads/{filename:path}")
async def serve_upload_file_options(filename: str):
    """Handle CORS preflight requests for uploads"""
    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

@app.options("/uploads/{filename:path}")
async def serve_upload_file_options(filename: str):
    """Handle CORS preflight requests for uploads"""
    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

@app.get("/uploads/{filename:path}")
@app.head("/uploads/{filename:path}")
async def serve_upload_file(filename: str, request: Request):
    """
    Serve uploaded files directly as raw bytes with proper headers for Instagram compatibility.
    
    Instagram's crawler requirements:
    - MUST return raw file bytes (not HTML wrapper)
    - MUST have correct Content-Type header (image/png, image/jpeg, video/mp4)
    - MUST be publicly accessible (no auth, no cookies required)
    - MUST support HEAD requests
    - MUST not redirect
    """
    import mimetypes
    
    file_path = uploads_path / filename
    
    # Security: prevent directory traversal
    try:
        resolved_path = file_path.resolve()
        resolved_uploads = uploads_path.resolve()
        if not str(resolved_path).startswith(str(resolved_uploads)):
            raise HTTPException(status_code=403, detail="Invalid file path")
    except (ValueError, OSError):
        raise HTTPException(status_code=403, detail="Invalid file path")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Determine Content-Type from file extension (Instagram is strict about this)
    ext = file_path.suffix.lower()
    content_type = None
    
    if ext in [".jpg", ".jpeg"]:
        content_type = "image/jpeg"
    elif ext == ".png":
        content_type = "image/png"
    elif ext in [".mp4", ".mov"]:
        content_type = "video/mp4"
    elif ext == ".gif":
        content_type = "image/gif"
    elif ext == ".webp":
        content_type = "image/webp"
    else:
        # Fallback to mimetypes detection
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"
    
    # Log for debugging (only in development)
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    if ENVIRONMENT == "development":
        user_agent = request.headers.get("User-Agent", "Unknown")
        print(f"DEBUG: Serving file {filename} | Content-Type: {content_type} | Size: {file_size} | User-Agent: {user_agent}")
    
    # Build headers that Instagram requires
    # CRITICAL: No cookies, no auth, no redirects
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(file_size),
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Cache-Control": "public, max-age=31536000",  # 1 year cache
        "Accept-Ranges": "bytes",
        # Explicitly don't set Set-Cookie header
        # Instagram's crawler doesn't send cookies and shouldn't receive them
    }
    
    # For HEAD requests, return headers only (no body)
    if request.method == "HEAD":
        from fastapi.responses import Response
        response = Response(
            status_code=200,
            headers=headers
        )
        # Explicitly prevent cookie setting
        response.delete_cookie = lambda *args, **kwargs: None
        return response
    
    # For GET requests, return raw file bytes
    # Using StreamingResponse with explicit file reading to ensure raw bytes
    from fastapi.responses import StreamingResponse
    
    def iterfile():
        with open(file_path, "rb") as f:
            # Read in chunks to avoid memory issues with large files
            while True:
                chunk = f.read(8192)  # 8KB chunks
                if not chunk:
                    break
                yield chunk
    
    response = StreamingResponse(
        iterfile(),
        media_type=content_type,
        headers=headers
    )
    # Explicitly prevent cookie setting
    response.delete_cookie = lambda *args, **kwargs: None
    return response

# Templates
templates_path = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(templates_path))

def render_template(template_name: str, context: dict):
    """Render Jinja2 template"""
    template = jinja_env.get_template(template_name)
    return template.render(**context)

# Include API router
app.include_router(api_router)
app.include_router(auth_router)

# --- Instagram webhook (for Meta app verification & development) ---
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "my_test_token_for_instagram_verification")


@app.get("/webhooks/instagram", response_class=PlainTextResponse)
async def webhook_instagram_verify(request: Request):
    """
    Meta sends GET with hub.mode, hub.verify_token, hub.challenge.
    Echo hub.challenge if verify_token matches. Use this URL as Callback URL in your app.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN and challenge:
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhooks/instagram")
async def webhook_instagram_events(request: Request):
    """Webhook verification (GET) is separate. POST: receive events, log payloads, forward comments/messages."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    try:
        process_webhook_payload(body, instaforge_app)
    except Exception as e:
        from src.utils.logger import get_logger
        get_logger(__name__).exception("Instagram webhook processing error", error=str(e))
    return {"status": "ok"}

# Global InstaForge app instance
instaforge_app: Optional[InstaForgeApp] = None


@app.on_event("startup")
async def startup_event():
    """Initialize InstaForge app on startup"""
    global instaforge_app
    try:
        # Only start Cloudflare tunnel in development (not in production with Apache)
        ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
        if ENVIRONMENT == "development":
            port = int(os.getenv("PORT", "8000"))
            print("Starting Cloudflare tunnel (development mode)...")
            start_cloudflare(port=port)
        else:
            print("Production mode: Skipping Cloudflare tunnel (using Apache reverse proxy)")
        
        instaforge_app = InstaForgeApp()
        instaforge_app.initialize()
        
        # Start comment monitoring for all accounts
        print("Starting comment automation...")
        instaforge_app.comment_monitor.start_monitoring_all_accounts()
        print("Comment automation started - monitoring posts for new comments")
        
        # Set app instance for API routes
        from .api import set_app_instance
        set_app_instance(instaforge_app)
        # Start background loop to publish scheduled posts when due
        start_scheduled_publisher(instaforge_app, interval_seconds=60)
        # Daily token refresh for OAuth accounts (tokens older than 40 days)
        start_daily_token_refresh_job(instaforge_app, interval_seconds=86400)
    except Exception as e:
        print(f"Warning: Failed to initialize InstaForge app: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global instaforge_app
    
    # Stop Cloudflare tunnel (only if it was started in development)
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    if ENVIRONMENT == "development":
        stop_cloudflare()
    
    if instaforge_app:
        stop_scheduled_publisher()
        stop_daily_token_refresh_job()
        if instaforge_app.comment_monitor:
            instaforge_app.comment_monitor.stop_monitoring_all_accounts()
        instaforge_app.shutdown()


# Route handlers for frontend pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main posting page"""
    content = render_template("index.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request):
    """Published posts page"""
    content = render_template("posts.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Logs viewer page"""
    content = render_template("logs.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration page"""
    content = render_template("config.html", {"request": request})
    return HTMLResponse(content=content)


# App instance is set in startup_event
