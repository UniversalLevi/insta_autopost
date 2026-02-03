"""FastAPI main application for InstaForge web dashboard"""

import sys
from pathlib import Path
from typing import Optional

import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send
from jinja2 import Environment, FileSystemLoader

from .api import router as api_router, auth_router
from .cloudflare_helper import start_cloudflare, stop_cloudflare, get_cloudflare_url
from .instagram_webhook import process_webhook_payload
from .scheduled_publisher import start_scheduled_publisher, stop_scheduled_publisher
from .warming_scheduler import start_warming_scheduler, stop_warming_scheduler
from .warmup_automation_scheduler import start_warmup_automation_scheduler, stop_warmup_automation_scheduler
from src.app import InstaForgeApp
from src.services.token_refresher import start_daily_token_refresh_job, stop_daily_token_refresh_job
from src.utils.logger import get_logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = get_logger(__name__)

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


# Authentication middleware (raw ASGI to avoid BaseHTTPMiddleware CancelledError on client disconnect)
PUBLIC_ROUTES = {
    "/login",
    "/register",
    "/auth/login",
    "/auth/logout",
    "/auth/register",
    "/auth/meta/login",
    "/auth/meta/callback",
    "/auth/meta/redirect-uri",
    "/webhooks/instagram",
    "/webhooks/instagram/",
    "/api/health",
}
PUBLIC_PREFIXES = ["/static/", "/uploads/"]


def _get_session_token_from_scope(scope: Scope) -> Optional[str]:
    """Extract session_token from ASGI scope (Cookie or Authorization header)."""
    headers = scope.get("headers") or []
    headers_lower = {k.decode("latin-1").lower(): v for k, v in headers}
    auth = headers_lower.get("authorization")
    if auth:
        auth_decoded = auth.decode("latin-1")
        if auth_decoded.startswith("Bearer "):
            return auth_decoded[7:].strip()
    cookie = headers_lower.get("cookie")
    if cookie:
        cookie_decoded = cookie.decode("latin-1")
        for part in cookie_decoded.split(";"):
            part = part.strip()
            if part.startswith("session_token="):
                return part.split("=", 1)[1].strip()
    return None


class AuthMiddlewareASGI:
    """Raw ASGI auth middleware; avoids request stream wrapping that causes CancelledError on disconnect."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        is_public = (
            path in PUBLIC_ROUTES
            or any(path.startswith(p) for p in PUBLIC_PREFIXES)
            or path.startswith("/api/")
            or path.startswith("/auth/")
        )
        if is_public:
            await self.app(scope, receive, send)
            return
        from src.auth.user_auth import validate_session
        token = _get_session_token_from_scope(scope)
        user = await run_in_threadpool(validate_session, token) if token else None
        if not user:
            headers_list = list(scope.get("headers") or [])
            accept = next((v for k, v in headers_list if k.lower() == b"accept"), b"")
            if accept.decode("latin-1", errors="replace").strip().startswith("text/html"):
                await send({
                    "type": "http.response.start",
                    "status": 302,
                    "headers": [[b"location", b"/login"]],
                })
                await send({"type": "http.response.body", "body": b""})
                return
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail":"Not authenticated"}',
            })
            return
        await self.app(scope, receive, send)


# Add authentication middleware (after CORS)
app.add_middleware(AuthMiddlewareASGI)

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Uploads directory: absolute path for reliable deployment (Render, Apache, etc.)
_web_dir = Path(__file__).resolve().parent
uploads_path = _web_dir.parent / "uploads"
uploads_path.mkdir(exist_ok=True)

# Direct file serving route for uploads (for better Instagram compatibility)
# IMPORTANT: This route MUST be public (no auth) and serve raw bytes with correct Content-Type
# Instagram's crawler requires: raw bytes, correct Content-Type, byte-range support for MP4
@app.options("/uploads/{filename:path}")
async def serve_upload_file_options(filename: str):
    """Handle CORS preflight requests for uploads"""
    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range",
            "Access-Control-Max-Age": "3600",
        }
    )


def _parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    """
    Parse Range header (bytes=start-end) and return (start, end) inclusive, or None.
    Instagram's crawler sends Range requests for MP4 streaming.
    """
    if not range_header or not range_header.strip().lower().startswith("bytes="):
        return None
    try:
        parts = range_header[6:].strip().split("-")
        if len(parts) != 2:
            return None
        start_str, end_str = parts[0].strip(), parts[1].strip()
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        if start < 0 or end >= file_size or start > end:
            return None
        return (start, end)
    except (ValueError, IndexError):
        return None


@app.get("/uploads/{filename:path}")
@app.head("/uploads/{filename:path}")
async def serve_upload_file(filename: str, request: Request):
    """
    Serve uploaded files with byte-range support for Instagram MP4 compatibility.
    
    Instagram's crawler requirements:
    - MUST return raw file bytes (not HTML wrapper)
    - MUST have correct Content-Type (image/*, video/mp4)
    - MUST be publicly accessible (no auth, no cookies)
    - MUST support HEAD and Range requests (byte-range for video streaming)
    - MUST not redirect
    """
    import mimetypes
    from fastapi.responses import Response, StreamingResponse

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
        user_agent = request.headers.get("User-Agent", "Unknown")[:100]
        logger.warning(
            "File not found for upload request",
            filename=filename,
            file_path=str(file_path),
            user_agent=user_agent,
        )
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    file_size = file_path.stat().st_size

    # Content-Type from extension (Instagram is strict)
    ext = file_path.suffix.lower()
    content_type = (
        "image/jpeg" if ext in [".jpg", ".jpeg"] else
        "image/png" if ext == ".png" else
        "video/mp4" if ext in [".mp4", ".mov"] else
        "image/gif" if ext == ".gif" else
        "image/webp" if ext == ".webp" else
        (mimetypes.guess_type(str(file_path))[0] or "application/octet-stream")
    )

    # Byte-range: Instagram sends Range for MP4; required for video streaming
    range_tuple = _parse_range_header(request.headers.get("Range"), file_size)

    # Base headers for Instagram compatibility
    base_headers = {
        "Content-Type": content_type,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Range",
        "Cache-Control": "public, max-age=31536000",
        "Accept-Ranges": "bytes",
    }

    user_agent = request.headers.get("User-Agent", "Unknown")
    logger.info(
        "Serving uploaded file",
        filename=filename,
        content_type=content_type,
        file_size=file_size,
        has_range=range_tuple is not None,
        user_agent=user_agent[:100],
        method=request.method,
    )

    # HEAD: return headers only
    if request.method == "HEAD":
        if range_tuple:
            start, end = range_tuple
            length = end - start + 1
            resp = Response(status_code=206, headers={
                **base_headers,
                "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
            })
        else:
            resp = Response(status_code=200, headers={
                **base_headers,
                "Content-Length": str(file_size),
            })
        resp.delete_cookie = lambda *a, **kw: None
        return resp

    # GET: full or partial content
    if range_tuple:
        start, end = range_tuple
        length = end - start + 1

        def iter_range():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                chunk_size = 8192
                while remaining > 0:
                    to_read = min(chunk_size, remaining)
                    chunk = f.read(to_read)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        response = StreamingResponse(
            iter_range(),
            media_type=content_type,
            status_code=206,
            headers={
                **base_headers,
                "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
            },
        )
    else:
        def iterfile():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk

        response = StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers={
                **base_headers,
                "Content-Length": str(file_size),
            },
        )

    response.delete_cookie = lambda *a, **kw: None
    if hasattr(response, "headers") and "Set-Cookie" in response.headers:
        del response.headers["Set-Cookie"]
    return response

# Templates
templates_path = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(templates_path))

def _render_template_sync(template_name: str, context: dict) -> str:
    """Sync Jinja2 render (used from threadpool to avoid blocking event loop)."""
    template = jinja_env.get_template(template_name)
    return template.render(**context)


async def render_template_async(template_name: str, context: dict) -> str:
    """Render Jinja2 template in threadpool so the event loop is not blocked."""
    return await run_in_threadpool(_render_template_sync, template_name, context)

# Include API router
app.include_router(api_router)
app.include_router(auth_router)

# --- Instagram webhook (for Meta app verification & development) ---
# Meta sends GET with hub.mode=subscribe&hub.verify_token=XXX&hub.challenge=YYY.
# We must return 200 with body = challenge (plain text). Use same value in Meta and WEBHOOK_VERIFY_TOKEN.
WEBHOOK_VERIFY_TOKEN = (os.environ.get("WEBHOOK_VERIFY_TOKEN") or "my_test_token_for_instagram_verification").strip()


def _webhook_verify_get(request: Request):
    """
    Handle Meta webhook verification GET. Echo hub.challenge if verify_token matches.
    Only treat as Meta verification when hub.mode=subscribe; otherwise return 200 so
    browser visits and health checks never get 403.
    """
    from src.utils.logger import get_logger
    webhook_logger = get_logger(__name__)

    mode = (request.query_params.get("hub.mode") or "").strip()
    token = (request.query_params.get("hub.verify_token") or "").strip()
    challenge = (request.query_params.get("hub.challenge") or "").strip()

    # Only run strict verification when Meta actually sends hub.mode=subscribe
    if mode == "subscribe":
        webhook_logger.info(
            "Instagram webhook verification request",
            has_token=bool(token),
            token_matches=(token == WEBHOOK_VERIFY_TOKEN) if token else False,
            has_challenge=bool(challenge),
            url=str(request.url),
        )
        if token == WEBHOOK_VERIFY_TOKEN and challenge:
            webhook_logger.info("Instagram webhook verification successful")
            return PlainTextResponse(content=challenge, status_code=200)
        webhook_logger.warning(
            "Instagram webhook verification failed (403). Use the same Verify token in Meta as WEBHOOK_VERIFY_TOKEN in .env.",
            token_matches=(token == WEBHOOK_VERIFY_TOKEN) if token else False,
        )
        raise HTTPException(
            status_code=403,
            detail="Verification failed: verify_token must match WEBHOOK_VERIFY_TOKEN",
        )

    # Not a Meta verification GET (browser visit, health check, or missing params): return 200
    return PlainTextResponse(
        content="Webhook endpoint OK. Use this URL as Callback URL in Meta; set Verify token to the value of WEBHOOK_VERIFY_TOKEN in .env.",
        status_code=200,
    )


@app.get("/webhooks/instagram", response_class=PlainTextResponse)
async def webhook_instagram_verify(request: Request):
    """Meta callback URL: GET with hub.mode, hub.verify_token, hub.challenge. Returns challenge on success."""
    return _webhook_verify_get(request)


@app.get("/webhooks/instagram/", response_class=PlainTextResponse)
async def webhook_instagram_verify_trailing_slash(request: Request):
    """Same as /webhooks/instagram so Meta validation works with or without trailing slash."""
    return _webhook_verify_get(request)


@app.post("/webhooks/instagram")
async def webhook_instagram_events(request: Request):
    """Webhook verification (GET) is separate. POST: receive events, log payloads, forward comments/messages."""
    from src.utils.logger import get_logger
    import json
    webhook_logger = get_logger(__name__)
    
    webhook_logger.info(
        "=== WEBHOOK POST RECEIVED ===",
        method=request.method,
        url=str(request.url),
        client_host=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        content_type=request.headers.get("content-type"),
    )
    
    # Try to read body
    try:
        body_bytes = await request.body()
        body_preview = body_bytes[:500].decode('utf-8', errors='ignore') if body_bytes else None
        
        webhook_logger.info(
            "Webhook body received",
            body_size=len(body_bytes),
            body_preview=body_preview,
        )
        
        # Parse JSON
        if body_bytes:
            body = json.loads(body_bytes)
        else:
            body = {}
        
        webhook_logger.info(
            "Instagram webhook body parsed",
            body_type=type(body).__name__,
            body_keys=list(body.keys()) if isinstance(body, dict) else None,
            has_object=bool(body.get("object") if isinstance(body, dict) else False),
            object_type=body.get("object") if isinstance(body, dict) else None,
        )
    except json.JSONDecodeError as e:
        webhook_logger.error(
            "Instagram webhook JSON parse failed",
            error=str(e),
            body_preview=body_bytes[:500].decode('utf-8', errors='ignore') if 'body_bytes' in locals() else None,
        )
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Invalid JSON"})
    except Exception as e:
        webhook_logger.exception("Instagram webhook body read failed", error=str(e))
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
    
    # Process webhook
    try:
        if instaforge_app is None:
            webhook_logger.error("InstaForge app not initialized")
            return JSONResponse(status_code=500, content={"status": "error", "detail": "App not initialized"})
        
        process_webhook_payload(body, instaforge_app)
        webhook_logger.info("Instagram webhook processing completed successfully")
    except Exception as e:
        webhook_logger.exception("Instagram webhook processing error", error=str(e))
    
    return JSONResponse(status_code=200, content={"status": "ok"})

# Global InstaForge app instance
instaforge_app: Optional[InstaForgeApp] = None


@app.on_event("startup")
async def startup_event():
    """Initialize InstaForge app on startup"""
    global instaforge_app
    try:
        # Only start Cloudflare tunnel in development when not already started by web_server.py
        ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
        if ENVIRONMENT == "development" and os.getenv("CLOUDFLARE_STARTED_BY_WEB_SERVER") != "1":
            port = int(os.getenv("PORT", os.getenv("WEB_PORT", "8000")))
            print("Starting Cloudflare tunnel (development mode)...")
            try:
                start_cloudflare(port=port)
            except Exception as e:
                logger.warning(f"Failed to start Cloudflare tunnel: {e}")
        
        instaforge_app = InstaForgeApp()
        instaforge_app.initialize()
        
        # Set app instance for API routes
        from .api import set_app_instance
        set_app_instance(instaforge_app)
        
        # Sleep mode: no scheduled posts, warming, comment monitor, token refresh, or health monitoring
        _sleep = (os.getenv("SLEEP_MODE") or os.getenv("PAUSE_ALL") or "").strip().lower() in ("1", "true", "yes")
        if _sleep:
            print("SLEEP MODE: Background tasks disabled (scheduled posts, warming, comment monitor, health). Set SLEEP_MODE=0 to enable.")
            logger.info("Sleep mode enabled - skipping scheduled publisher, warming, comment monitor, token refresh, health monitoring")
        else:
            # Start comment monitoring for all accounts
            print("Starting comment automation...")
            try:
                instaforge_app.comment_monitor.start_monitoring_all_accounts()
                print("Comment automation started - monitoring posts for new comments")
            except Exception as e:
                logger.error(f"Failed to start comment monitoring: {e}", exc_info=True)
            
            # Start background loop to publish scheduled posts when due
            try:
                start_scheduled_publisher(instaforge_app, interval_seconds=60)
            except Exception as e:
                logger.error(f"Failed to start scheduled publisher: {e}", exc_info=True)
            
            # Daily token refresh for OAuth accounts (tokens older than 40 days)
            try:
                start_daily_token_refresh_job(instaforge_app, interval_seconds=86400)
            except Exception as e:
                logger.error(f"Failed to start token refresh job: {e}", exc_info=True)
            
            # Start warming scheduler
            print("Starting warming scheduler...")
            try:
                start_warming_scheduler(instaforge_app)
                print("Warming scheduler started - warming actions will run at scheduled time")
            except Exception as e:
                logger.error(f"Failed to start warming scheduler: {e}", exc_info=True)
                print(f"Warning: Warming scheduler failed to start: {e}")

            # Start warm-up automation scheduler
            try:
                start_warmup_automation_scheduler(instaforge_app)
                print("Warm-up automation scheduler started")
            except Exception as e:
                logger.error(f"Failed to start warmup automation scheduler: {e}", exc_info=True)
            
            # Start account health monitoring
            if instaforge_app.account_health_service:
                try:
                    instaforge_app.account_health_service.start_monitoring()
                    print("Account health monitoring started")
                except Exception as e:
                    logger.error(f"Failed to start account health monitoring: {e}", exc_info=True)
        
        print("InstaForge startup completed successfully!")
    except Exception as e:
        logger.exception("Critical error during startup", error=str(e))
        print(f"ERROR: Failed to initialize InstaForge app: {e}")
        print("The application may not function correctly. Check the logs for details.")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global instaforge_app
    
    logger.info("Shutdown event triggered - stopping all services")
    
    # Stop Cloudflare tunnel (only if it was started in development)
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    if ENVIRONMENT == "development":
        try:
            stop_cloudflare()
        except Exception as e:
            logger.warning("Error stopping Cloudflare tunnel", error=str(e))
    
    if instaforge_app:
        # Stop all background services (order matters - stop monitors first)
        try:
            if instaforge_app.comment_monitor:
                logger.info("Stopping comment monitor...")
                instaforge_app.comment_monitor.stop_monitoring_all_accounts()
        except BaseException as e:
            logger.warning("Error stopping comment monitor", error=str(e))
            # Do not re-raise: allow remaining shutdown steps to run
        
        try:
            if instaforge_app.account_health_service:
                logger.info("Stopping health monitoring...")
                instaforge_app.account_health_service.stop_monitoring()
        except Exception as e:
            logger.warning("Error stopping health monitoring", error=str(e))
        
        try:
            logger.info("Stopping scheduled publisher...")
            stop_scheduled_publisher()
        except Exception as e:
            logger.warning("Error stopping scheduled publisher", error=str(e))
        
        try:
            logger.info("Stopping token refresher...")
            stop_daily_token_refresh_job()
        except Exception as e:
            logger.warning("Error stopping token refresher", error=str(e))
        
        try:
            logger.info("Stopping warming scheduler...")
            stop_warming_scheduler()
        except Exception as e:
            logger.warning("Error stopping warming scheduler", error=str(e))

        try:
            logger.info("Stopping warmup automation scheduler...")
            stop_warmup_automation_scheduler()
        except Exception as e:
            logger.warning("Error stopping warmup automation scheduler", error=str(e))
        
        # Close browser automation with await (we're in async context; sync close_all uses run_until_complete on same loop → fails)
        try:
            if getattr(instaforge_app, "browser_wrapper", None) and instaforge_app.browser_wrapper:
                logger.info("Closing browser automation...")
                await instaforge_app.browser_wrapper.browser_service.close_all()
        except Exception as e:
            logger.warning("Error closing browser automation", error=str(e))
        
        try:
            logger.info("Shutting down app...")
            instaforge_app.shutdown(skip_browser_close=True)
        except Exception as e:
            logger.warning("Error in app shutdown", error=str(e))
    
    logger.info("Shutdown complete")


# Route handlers for frontend pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main posting page"""
    content = await render_template_async("index.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request):
    """Scheduled posts queue page"""
    content = await render_template_async("schedule.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request):
    """Published posts page"""
    content = await render_template_async("posts.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Logs viewer page"""
    content = await render_template_async("logs.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    """Account status dashboard page"""
    content = await render_template_async("accounts.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/warmup", response_class=HTMLResponse)
async def warmup_page(request: Request):
    """5-Day Account Warm-Up dashboard page"""
    content = await render_template_async("warmup.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/webhook-test", response_class=HTMLResponse)
async def webhook_test_page(request: Request):
    """Webhook and AI DM test page"""
    from .webhook_config import get_webhook_config
    webhook_config = get_webhook_config()
    content = await render_template_async(
        "webhook-test.html",
        {"request": request, "webhook_config": webhook_config}
    )
    return HTMLResponse(content=content)


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration page"""
    content = await render_template_async("config.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/ai-settings", response_class=HTMLResponse)
async def ai_settings_page(request: Request):
    """AI Settings page"""
    content = await render_template_async("ai-settings.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/inbox", response_class=HTMLResponse)
async def inbox_page(request: Request):
    """AI DM Inbox - view users, messages, AI suggestions, approve/send"""
    content = await render_template_async("inbox.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    content = await render_template_async("login.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    content = await render_template_async("register.html", {"request": request})
    return HTMLResponse(content=content)


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """User management page (admin only)"""
    # Check if user is admin (middleware already checked auth)
    from web.auth_deps import get_session_token
    from src.auth.user_auth import validate_session
    
    token = get_session_token(request)
    user = await run_in_threadpool(validate_session, token) if token else None
    
    if not user or user.role != "admin":
        return RedirectResponse(url="/", status_code=302)
    
    content = await render_template_async("users.html", {"request": request})
    return HTMLResponse(content=content)


# App instance is set in startup_event
