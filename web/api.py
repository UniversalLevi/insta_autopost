"""API route handlers for InstaForge web dashboard"""

import json
import yaml
import os
import uuid
import shutil
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import HttpUrl, BaseModel

from .models import (
    CreatePostRequest,
    PostResponse,
    LogEntry,
    ConfigAccountResponse,
    ConfigSettingsResponse,
    StatusResponse,
    PublishedPostResponse,
)
from src.models.post import PostMedia, Post, PostStatus
from src.models.account import Account, ProxyConfig, WarmingConfig, CommentToDMConfig
from src.app import InstaForgeApp
from src.utils.config import config_manager, Settings
from src.services.scheduled_posts_store import add_scheduled


router = APIRouter(prefix="/api", tags=["api"])

# Global InstaForge app instance (set by main.py)
_app_instance: Optional[InstaForgeApp] = None


def set_app_instance(instance: InstaForgeApp):
    """Set the global app instance"""
    global _app_instance
    _app_instance = instance


def get_app() -> InstaForgeApp:
    """Dependency to get InstaForge app instance"""
    if _app_instance is None:
        raise HTTPException(status_code=500, detail="Application not initialized")
    return _app_instance


# --- Account Management Endpoints ---

@router.get("/config/accounts")
async def get_accounts():
    """List all accounts"""
    accounts = config_manager.load_accounts()
    return {"accounts": [acc.dict() for acc in accounts]}

@router.post("/config/accounts/add")
async def add_account(account: Account, app: InstaForgeApp = Depends(get_app)):
    """Add a new account"""
    try:
        accounts = config_manager.load_accounts()
        
        # Check for duplicate ID
        if any(acc.account_id == account.account_id for acc in accounts):
            raise HTTPException(status_code=400, detail=f"Account ID {account.account_id} already exists")
            
        accounts.append(account)
        config_manager.save_accounts(accounts)
        
        # Reload app state
        app.accounts = accounts
        app.account_service.update_accounts(accounts)
        
        return {"status": "success", "message": "Account added", "account": account.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add account: {str(e)}")

@router.put("/config/accounts/{account_id}")
async def update_account(account_id: str, account_update: Account, app: InstaForgeApp = Depends(get_app)):
    """Update an existing account"""
    try:
        # Ensure ID matches
        if account_id != account_update.account_id:
            raise HTTPException(status_code=400, detail="Account ID in path must match body")
            
        accounts = config_manager.load_accounts()
        
        found = False
        for i, acc in enumerate(accounts):
            if acc.account_id == account_id:
                accounts[i] = account_update
                found = True
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="Account not found")
            
        config_manager.save_accounts(accounts)
        
        # Reload app state
        app.accounts = accounts
        app.account_service.update_accounts(accounts)
        
        return {"status": "success", "message": "Account updated", "account": account_update.dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update account: {str(e)}")

@router.delete("/config/accounts/{account_id}")
async def delete_account(account_id: str, app: InstaForgeApp = Depends(get_app)):
    """Delete an account"""
    try:
        accounts = config_manager.load_accounts()
        
        initial_len = len(accounts)
        accounts = [acc for acc in accounts if acc.account_id != account_id]
        
        if len(accounts) == initial_len:
            raise HTTPException(status_code=404, detail="Account not found")
            
        config_manager.save_accounts(accounts)
        
        # Reload app state
        app.accounts = accounts
        app.account_service.update_accounts(accounts)
        
        return {"status": "success", "message": "Account deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")

# --- Global Settings Endpoints ---

@router.get("/config/settings")
async def get_settings():
    """Get global settings"""
    settings = config_manager.load_settings()
    return settings.dict()

@router.put("/config/settings")
async def update_settings(settings: Settings, app: InstaForgeApp = Depends(get_app)):
    """Update global settings"""
    try:
        config_manager.save_settings(settings)
        
        # Reload app config (partial reload)
        app.config = settings
        # Trigger any necessary service updates here
        # For example, rate limiter might need update if limits changed
        if app.rate_limiter:
            app.rate_limiter.requests_per_hour = settings.instagram.rate_limit["requests_per_hour"]
            app.rate_limiter.requests_per_minute = settings.instagram.rate_limit["requests_per_minute"]
            
        return {"status": "success", "message": "Settings updated", "settings": settings.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


# --- Execution Endpoints ---

@router.post("/posts/create", response_model=PostResponse)
async def create_post(request: Request, post_data: CreatePostRequest, app: InstaForgeApp = Depends(get_app)):
    """Create a new post"""
    try:
        # Handle reels (treat as video)
        media_type = "video" if post_data.media_type == "reels" else post_data.media_type
        
        # Build PostMedia object
        if media_type == "carousel":
            if len(post_data.urls) < 2:
                raise HTTPException(status_code=400, detail=f"Carousel posts require 2-10 items. Provided: {len(post_data.urls)}")
            if len(post_data.urls) > 10:
                raise HTTPException(status_code=400, detail=f"Carousel posts max 10 items. Provided: {len(post_data.urls)}")
            
            children = []
            for url in post_data.urls:
                url_lower = url.lower()
                child_type = "image"
                if url_lower.endswith((".mp4", ".mov", ".avi", ".mkv")):
                    child_type = "video"
                children.append(PostMedia(media_type=child_type, url=HttpUrl(url)))
            
            media = PostMedia(media_type="carousel", children=children, caption=post_data.caption)
        else:
            if not post_data.urls or len(post_data.urls) != 1:
                raise HTTPException(status_code=400, detail=f"{media_type.capitalize()} posts require exactly 1 URL.")
            
            # Infer media_type from URL so .mp4 etc. are never sent as image (fixes Instagram timeout)
            url0 = post_data.urls[0].lower()
            if url0.endswith((".mp4", ".mov", ".avi", ".mkv")):
                media_type = "video"
            
            media = PostMedia(media_type=media_type, url=HttpUrl(post_data.urls[0]), caption=post_data.caption)
        
        # Localhost check (always, including scheduled)
        for url in post_data.urls:
            if "localhost" in url or "127.0.0.1" in url or url.startswith("http://"):
                raise HTTPException(status_code=400, detail="Instagram requires public HTTPS URLs.")

        is_scheduled = post_data.scheduled_time is not None

        if is_scheduled:
            # Persist scheduled post; publish later via background job
            sid = add_scheduled(
                account_id=post_data.account_id,
                media_type=media_type,
                urls=post_data.urls,
                caption=post_data.caption or "",
                scheduled_time=post_data.scheduled_time,
                hashtags=post_data.hashtags,
            )
            post = await run_in_threadpool(
                app.posting_service.create_post,
                account_id=post_data.account_id,
                media=media,
                caption=post_data.caption,
                scheduled_time=post_data.scheduled_time,
            )
            post.hashtags = post_data.hashtags or []
            return PostResponse(
                post_id=sid,
                account_id=post.account_id,
                media_type=media_type,
                caption=post.caption,
                hashtags=post.hashtags,
                status="scheduled",
                instagram_media_id=None,
                published_at=None,
                created_at=post.created_at,
                error_message=None,
            )
        # Immediate publish
        post = await run_in_threadpool(
            app.posting_service.create_post,
            account_id=post_data.account_id,
            media=media,
            caption=post_data.caption,
            scheduled_time=None,
        )
        post.hashtags = post_data.hashtags or []
        try:
            post = await run_in_threadpool(app.posting_service.publish_post, post)
        except Exception as e:
            post.status = PostStatus.FAILED
            post.error_message = str(e)
            raise HTTPException(status_code=400, detail=f"Publishing failed: {str(e)}")
        return PostResponse(
            post_id=str(post.post_id) if post.post_id else None,
            account_id=post.account_id,
            media_type=media_type,
            caption=post.caption,
            hashtags=post.hashtags,
            status=str(post.status),
            instagram_media_id=str(post.instagram_media_id) if post.instagram_media_id else None,
            published_at=post.published_at,
            created_at=post.created_at,
            error_message=post.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")

@router.get("/posts/published")
async def get_published_posts(request: Request, limit: int = 20, account_id: Optional[str] = None, app: InstaForgeApp = Depends(get_app)):
    """Fetch published posts from Instagram API"""
    try:
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        client = app.account_service.get_client(account_id)
        media_list = await run_in_threadpool(client.get_recent_media, limit=limit)
        
        posts = []
        for media in media_list:
            posts.append(PublishedPostResponse(
                id=media.get("id", ""),
                media_type=media.get("media_type"),
                caption=media.get("caption", ""),
                permalink=media.get("permalink"),
                timestamp=media.get("timestamp"),
            ))
        
        return {"posts": posts, "count": len(posts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch posts: {str(e)}")

@router.get("/logs")
async def get_logs(lines: int = 100, level: Optional[str] = None):
    """Get recent log entries"""
    settings = config_manager.load_settings()
    fp = settings.logging.file_path
    # Resolve relative to project root (web/api.py -> web -> project root)
    project_root = Path(__file__).resolve().parent.parent
    log_path = (project_root / fp) if not Path(fp).is_absolute() else Path(fp)

    if not log_path.exists():
        return {"logs": [], "count": 0}
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        log_entries = []
        for line in recent_lines:
            try:
                log_data = json.loads(line.strip())
                log_level = log_data.get("level", "info").upper()
                
                if level and log_level != level.upper():
                    continue
                
                # Extract fields based on new structured logging format
                # Structlog JSON format usually has: timestamp, level, event/message
                log_entries.append(LogEntry(
                    timestamp=log_data.get("timestamp", ""),
                    level=log_level,
                    event=log_data.get("event", "Log"), # Event might be missing or same as message
                    message=log_data.get("message", "") or log_data.get("event", ""),
                    data={k: v for k, v in log_data.items() if k not in ["timestamp", "level", "event", "message"]},
                ))
            except json.JSONDecodeError:
                continue
        
        log_entries.reverse()
        return {"logs": log_entries, "count": len(log_entries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {str(e)}")


# --- Status & Utils ---

@router.get("/status", response_model=StatusResponse)
async def get_status(app: InstaForgeApp = Depends(get_app)):
    """Get system status"""
    try:
        accounts = app.account_service.list_accounts()
        
        account_list = []
        warming_enabled = False
        
        for account in accounts:
            is_warming = account.warming.enabled if account.warming else False
            if is_warming:
                warming_enabled = True
            
            account_list.append({
                "account_id": account.account_id,
                "username": account.username,
                "warming_enabled": is_warming,
            })
        
        warming_schedule = app.config.warming.schedule_time if app.config else "09:00"
        
        return StatusResponse(
            app_status="running",
            accounts=account_list,
            warming_enabled=warming_enabled,
            warming_schedule=warming_schedule,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.post("/upload")
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    """Upload media files"""
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        uploaded_urls = []
        from .cloudflare_helper import get_base_url
        base_url = get_base_url(str(request.base_url))
        
        for file in files:
            if not file.content_type or not (file.content_type.startswith("image/") or file.content_type.startswith("video/")):
                 raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}")
            
            file_ext = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = upload_dir / unique_filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_url = f"{base_url}/uploads/{unique_filename}?t={int(datetime.utcnow().timestamp())}"
            uploaded_urls.append({
                "url": file_url,
                "originalName": file.filename,
                "size": file_path.stat().st_size,
                "type": file.content_type,
            })
            
        return {"urls": uploaded_urls, "count": len(uploaded_urls)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload: {str(e)}")

@router.get("/test/verify-url")
async def verify_url(url: str):
    """Test URL accessibility"""
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "image/*,video/*"}
        response = await run_in_threadpool(requests.head, url, headers=headers, timeout=10, allow_redirects=True)
        return {
            "url": url,
            "status_code": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "is_valid": response.status_code == 200,
        }
    except Exception as e:
        return {"url": url, "error": str(e), "is_valid": False}


@router.get("/webhooks/callback-url")
async def get_webhook_callback_url():
    """
    Return the Instagram webhook callback URL for Meta app configuration.
    Use the Cloudflare tunnel URL when available (development/testing).
    IMPORTANT: In Meta, set Callback URL to the value of callback_url below.
    Do NOT use this /api/webhooks/callback-url endpoint as the Callback URL.
    """
    from .cloudflare_helper import get_cloudflare_url
    verify_token = os.environ.get("WEBHOOK_VERIFY_TOKEN", "my_test_token_for_instagram_verification")
    base = get_cloudflare_url()
    if base:
        callback_url = f"{base.rstrip('/')}/webhooks/instagram"
        return {
            "callback_url": callback_url,
            "verify_token": verify_token,
            "note": "In Meta app: Callback URL = callback_url above; Verify token = verify_token above. Do NOT use /api/webhooks/callback-url as Callback URL.",
        }
    return {
        "callback_url": None,
        "verify_token": verify_token,
        "note": "Start the app to create a Cloudflare tunnel, then GET this again for callback_url.",
    }


# --- Comment-to-DM Endpoints ---

@router.get("/comment-to-dm/status")
async def get_comment_to_dm_status(account_id: Optional[str] = None, app: InstaForgeApp = Depends(get_app)):
    """Get comment-to-DM status"""
    try:
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Service not initialized")
            
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
            
        status_info = app.comment_to_dm_service.get_status(account_id)
        return {"account_id": account_id, "status": status_info}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/comment-to-dm/config")
async def get_comment_to_dm_config(account_id: Optional[str] = None):
    """Get comment-to-DM config"""
    try:
        accounts = config_manager.load_accounts()
        if not account_id:
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts found")
            account = accounts[0]
            account_id = account.account_id
        else:
            account = next((a for a in accounts if a.account_id == account_id), None)
            if not account:
                raise HTTPException(status_code=404, detail="Account not found")
        
        return {
            "account_id": account_id,
            "config": account.comment_to_dm.dict() if account.comment_to_dm else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

@router.put("/comment-to-dm/config")
async def update_comment_to_dm_config(request: Request, account_id: Optional[str] = None, app: InstaForgeApp = Depends(get_app)):
    """Update comment-to-DM config"""
    try:
        body = await request.json()
        accounts = config_manager.load_accounts()
        
        if not account_id:
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts found")
            account_idx = 0
            account = accounts[0]
            account_id = account.account_id
        else:
            found = False
            for i, acc in enumerate(accounts):
                if acc.account_id == account_id:
                    account_idx = i
                    account = acc
                    found = True
                    break
            if not found:
                raise HTTPException(status_code=404, detail="Account not found")
        
        # Update config
        new_config_data = account.comment_to_dm.dict() if account.comment_to_dm else {}
        new_config_data.update({
            "enabled": body.get("enabled", False),
            "trigger_keyword": body.get("trigger_keyword", "AUTO"),
            "dm_message_template": body.get("dm_message_template", ""),
            "link_to_send": body.get("link_to_send", ""),
        })
        
        # Helper to filter out None values if needed, but dict() should handle defaults if we reconstruct
        # But we need to update the account object
        account_data = account.dict()
        account_data['comment_to_dm'] = new_config_data
        
        # Validate and replace
        updated_account = Account(**account_data)
        accounts[account_idx] = updated_account
        
        config_manager.save_accounts(accounts)
        
        # Reload app
        app.accounts = accounts
        app.account_service.update_accounts(accounts)
        
        return {"status": "success", "account_id": account_id, "config": updated_account.comment_to_dm.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

@router.post("/comment-to-dm/post/{media_id}/file")
async def set_post_dm_file(request: Request, media_id: str, account_id: Optional[str] = None, app: InstaForgeApp = Depends(get_app)):
    """Set post specific DM file"""
    try:
        body = await request.json()
        file_path = body.get("file_path")
        file_url = body.get("file_url")
        trigger_mode = body.get("trigger_mode", "AUTO")
        trigger_word = body.get("trigger_word")
        
        if not file_url and not file_path:
             raise HTTPException(status_code=400, detail="File URL or path required")
             
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Service not initialized")

        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                 raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
            
        app.comment_to_dm_service.post_dm_config.set_post_dm_file(
            account_id=account_id,
            media_id=media_id,
            file_path=file_path,
            file_url=file_url,
            trigger_mode=trigger_mode,
            trigger_word=trigger_word,
        )
        
        return {
            "status": "success",
            "account_id": account_id,
            "media_id": media_id,
            "file_url": file_url or file_path,
            "trigger_mode": trigger_mode,
            "trigger_word": trigger_word,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set post DM: {str(e)}")

@router.get("/comment-to-dm/post/{media_id}/file")
async def get_post_dm_file(media_id: str, account_id: Optional[str] = None, app: InstaForgeApp = Depends(get_app)):
    """Get post specific DM config"""
    try:
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Service not initialized")
            
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                 raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
            
        config = app.comment_to_dm_service.post_dm_config.get_post_dm_config(
            account_id=account_id,
            media_id=media_id,
        )
        
        if config:
            return {
                "account_id": account_id,
                "media_id": media_id,
                "file_url": config.get("file_url"),
                "trigger_mode": config.get("trigger_mode", "AUTO"),
                "trigger_word": config.get("trigger_word"),
                "has_config": True,
            }
        return {"account_id": account_id, "media_id": media_id, "has_config": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get post DM: {str(e)}")

@router.delete("/comment-to-dm/post/{media_id}/file")
async def remove_post_dm_file(media_id: str, account_id: Optional[str] = None, app: InstaForgeApp = Depends(get_app)):
    """Remove post specific DM config"""
    try:
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Service not initialized")
            
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                 raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
            
        app.comment_to_dm_service.post_dm_config.remove_post_dm_file(
            account_id=account_id,
            media_id=media_id,
        )
        return {"status": "success", "account_id": account_id, "media_id": media_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove post DM: {str(e)}")
