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
from pydantic import HttpUrl

from .auth import require_auth, check_password, create_session, destroy_session
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
from src.app import InstaForgeApp


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


def check_auth(request: Request):
    """Dependency to check authentication"""
    session_id = require_auth(request)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return session_id


# Authentication endpoints
@router.post("/login")
async def login(request: Request, password: str = None):
    """Login with password"""
    if password is None:
        body = await request.json()
        password = body.get("password", "")
    
    if not check_password(password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    
    session_id = create_session()
    response = JSONResponse({"status": "success", "session_id": session_id})
    response.set_cookie(
        key="instaforge_session",
        value=session_id,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    """Logout and destroy session"""
    session_id = request.cookies.get("instaforge_session")
    if session_id:
        destroy_session(session_id)
    return {"status": "success"}


@router.get("/auth/status")
async def auth_status(request: Request):
    """Check authentication status"""
    session_id = require_auth(request)
    return {"authenticated": True, "session_id": session_id}


# Posting endpoints
@router.post("/posts/create", response_model=PostResponse)
async def create_post(request: Request, post_data: CreatePostRequest, _auth=Depends(check_auth), app: InstaForgeApp = Depends(get_app)):
    """Create a new post"""
    try:
        # Handle reels (treat as video)
        media_type = "video" if post_data.media_type == "reels" else post_data.media_type
        
        # Build PostMedia object
        if media_type == "carousel":
            # Instagram requires 2-10 items for carousel posts
            if len(post_data.urls) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"Carousel posts require 2-10 media items. You provided {len(post_data.urls)}. Please add more files or select a different media type (Image/Video)."
                )
            if len(post_data.urls) > 10:
                raise HTTPException(
                    status_code=400,
                    detail=f"Carousel posts can have maximum 10 items. You provided {len(post_data.urls)}. Please remove {len(post_data.urls) - 10} file(s)."
                )
            
            # Create children for carousel
            children = []
            for url in post_data.urls:
                # Determine media type from URL extension
                url_lower = url.lower()
                if url_lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
                    child_type = "image"
                elif url_lower.endswith((".mp4", ".mov", ".avi", ".mkv")):
                    child_type = "video"
                else:
                    # Default to image if unknown
                    child_type = "image"
                
                children.append(PostMedia(
                    media_type=child_type,
                    url=HttpUrl(url),
                ))
            
            media = PostMedia(
                media_type="carousel",
                children=children,
                caption=post_data.caption,
            )
        else:
            # Single media - validate we have exactly one URL
            if not post_data.urls or len(post_data.urls) == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"{media_type.capitalize()} posts require 1 media URL. Please upload or provide a URL."
                )
            if len(post_data.urls) > 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"{media_type.capitalize()} posts require exactly 1 media URL. You provided {len(post_data.urls)}. Use Carousel type for multiple files or select only one file."
                )
            
            media = PostMedia(
                media_type=media_type,
                url=HttpUrl(post_data.urls[0]),
                caption=post_data.caption,
            )
        
        # Create post using existing service
        post = app.posting_service.create_post(
            account_id=post_data.account_id,
            media=media,
            caption=post_data.caption,
            scheduled_time=post_data.scheduled_time,
        )
        
        # Set hashtags on the post object
        post.hashtags = post_data.hashtags or []
        
        # If not scheduled, publish immediately
        if not post_data.scheduled_time:
            # Check if URLs are localhost - Instagram can't access them
            for url in post_data.urls:
                if "localhost" in url or "127.0.0.1" in url or url.startswith("http://"):
                    error_msg = (
                        "Instagram cannot access localhost URLs or HTTP URLs. "
                        "Media URLs must be publicly accessible HTTPS URLs. "
                        "Make sure ngrok is running and set NGROK_AUTHTOKEN. "
                        f"Current URL: {url}"
                    )
                    raise HTTPException(status_code=400, detail=error_msg)
            
            # Log the URL being used (for debugging)
            print(f"DEBUG: Publishing post with media URL: {post_data.urls[0]}")
            
            try:
                post = app.posting_service.publish_post(post)
            except Exception as e:
                # Log the error for debugging
                error_msg = str(e)
                print(f"DEBUG: Post publishing failed: {error_msg}")
                print(f"DEBUG: Media URL was: {post_data.urls[0]}")
                
                # Enhance error message for common issues
                if "9004" in error_msg or "media type" in error_msg.lower():
                    url = post_data.urls[0]
                    original_error = error_msg
                    
                    # Check if it's a Cloudflare tunnel URL
                    is_cloudflare_tunnel = "trycloudflare.com" in url or "cfargotunnel.com" in url
                    
                    if is_cloudflare_tunnel:
                        error_msg = (
                            "Instagram cannot access the media URL. "
                            "Cloudflare's trycloudflare.com is blocking Instagram's bot.\n\n"
                            "SOLUTION: Use a production static file host instead:\n"
                            "• AWS S3 (recommended)\n"
                            "• Cloudinary\n"
                            "• Firebase Storage\n"
                            "• DigitalOcean Spaces\n"
                            "• Supabase Storage\n\n"
                            f"Media URL used: {url}\n"
                            f"Original error: {original_error}"
                        )
                    else:
                        error_msg = (
                            "Instagram rejected the media URL (error 9004). Possible reasons:\n"
                            "1) The URL is not publicly accessible\n"
                            "2) The URL must be HTTPS (not HTTP)\n"
                            "3) Instagram's servers cannot fetch the media\n"
                            "4) The file may not be served correctly\n"
                            "5) The server is blocking Instagram's bot\n\n"
                            f"Media URL used: {url}\n"
                            f"Original error: {original_error}"
                        )
                
                # Return 400 Bad Request instead of 200 OK
                raise HTTPException(status_code=400, detail=error_msg)
        
        # Convert to response model
        # Post.status is already a string due to use_enum_values=True, not an enum instance
        # So we use post.status directly, not post.status.value
        return PostResponse(
            post_id=str(post.post_id) if post.post_id else None,
            account_id=post.account_id,
            media_type=media_type,
            caption=post.caption,
            hashtags=post.hashtags,
            status=str(post.status),  # Already a string, but ensure it's a string for safety
            instagram_media_id=str(post.instagram_media_id) if post.instagram_media_id else None,
            published_at=post.published_at,
            created_at=post.created_at,
            error_message=post.error_message,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific Instagram API errors
        if "OAuthException" in error_msg or "Invalid parameter" in error_msg or "code: 100" in error_msg:
            enhanced_msg = (
                "Instagram API Error: Invalid parameter or OAuth issue.\n\n"
                "Possible causes:\n"
                "1) Access token expired or invalid\n"
                "2) Missing required permissions (instagram_content_publish)\n"
                "3) Account not connected properly\n"
                "4) Media URL format issue\n\n"
                f"Original error: {error_msg}\n\n"
                "Solution: Regenerate your access token with correct permissions."
            )
            raise HTTPException(status_code=400, detail=enhanced_msg)
        
        if "too little or too many attachments" in error_msg or "carousel" in error_msg.lower():
            enhanced_msg = (
                "Instagram Carousel Error:\n\n"
                "Carousel posts require 2-10 media items.\n"
                "You selected 'Carousel' but:\n"
                f"- Provided {len(post_data.urls) if 'post_data' in locals() else 'unknown'} item(s)\n\n"
                "Solution:\n"
                "- For 1 file: Select 'Image' or 'Video' instead of 'Carousel'\n"
                "- For 2-10 files: Select 'Carousel' and upload 2-10 files\n"
                f"\nOriginal error: {error_msg}"
            )
            raise HTTPException(status_code=400, detail=enhanced_msg)
        
        raise HTTPException(status_code=400, detail=f"Failed to create post: {error_msg}")


@router.post("/posts/{post_id}/publish", response_model=PostResponse)
async def publish_post(request: Request, post_id: str, _auth=Depends(check_auth), app: InstaForgeApp = Depends(get_app)):
    """Publish an existing post"""
    # Note: This is a simplified version - in production, you'd store posts in a database
    # For now, we'll need to recreate the post from the request or store it temporarily
    raise HTTPException(status_code=501, detail="Post publishing requires post storage - implement database first")


@router.get("/posts/published")
async def get_published_posts(request: Request, limit: int = 20, account_id: Optional[str] = None, _auth=Depends(check_auth), app: InstaForgeApp = Depends(get_app)):
    """Fetch published posts from Instagram API"""
    try:
        # Get account ID (use first account if not specified)
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        # Get client and fetch recent media
        client = app.account_service.get_client(account_id)
        media_list = client.get_recent_media(limit=limit)
        
        # Convert to response format
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch published posts: {str(e)}")


# Logs endpoints
@router.get("/logs")
async def get_logs(request: Request, lines: int = 100, level: Optional[str] = None, _auth=Depends(check_auth)):
    """Get recent log entries"""
    log_path = Path("logs/instaforge.log")
    
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
                
                # Filter by level if specified
                if level and log_level != level.upper():
                    continue
                
                log_entries.append(LogEntry(
                    timestamp=log_data.get("timestamp", ""),
                    level=log_level,
                    event=log_data.get("event", "Unknown"),
                    message=log_data.get("message", ""),
                    data={k: v for k, v in log_data.items() if k not in ["timestamp", "level", "event", "message"]},
                ))
            except json.JSONDecodeError:
                # Skip invalid JSON lines
                continue
        
        # Reverse to show newest first
        log_entries.reverse()
        
        return {"logs": log_entries, "count": len(log_entries)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {str(e)}")


# Configuration endpoints
@router.get("/config/accounts")
async def get_account_config(request: Request, _auth=Depends(check_auth), app: InstaForgeApp = Depends(get_app)):
    """Get account configurations"""
    try:
        accounts = app.account_service.list_accounts()
        configs = []
        
        for account in accounts:
            configs.append(ConfigAccountResponse(
                account_id=account.account_id,
                username=account.username,
                warming_enabled=account.warming.enabled if account.warming else False,
                daily_actions=account.warming.daily_actions if account.warming else 0,
                action_types=account.warming.action_types if account.warming else [],
            ))
        
        return {"accounts": configs}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load account config: {str(e)}")


@router.get("/config/settings")
async def get_settings(request: Request, _auth=Depends(check_auth), app: InstaForgeApp = Depends(get_app)):
    """Get app settings"""
    try:
        config = app.config
        if not config:
            raise HTTPException(status_code=500, detail="Configuration not loaded")
        
        return ConfigSettingsResponse(
            warming_schedule_time=config.warming.schedule_time,
            rate_limit_per_hour=config.instagram.rate_limit["requests_per_hour"],
            rate_limit_per_minute=config.instagram.rate_limit["requests_per_minute"],
            posting_max_retries=config.instagram.posting["max_retries"],
            posting_retry_delay=config.instagram.posting["retry_delay_seconds"],
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")


@router.put("/config/accounts")
async def update_account_config(request: Request, _auth=Depends(check_auth)):
    """Update account configuration"""
    try:
        # Get request body
        body = await request.json()
        account_id = body.get("account_id")
        
        if not account_id:
            raise HTTPException(status_code=400, detail="account_id is required")
        
        # Load accounts.yaml
        accounts_path = Path("config/accounts.yaml")
        if not accounts_path.exists():
            raise HTTPException(status_code=404, detail="Accounts config file not found")
        
        with open(accounts_path, "r") as f:
            accounts_data = yaml.safe_load(f)
        
        # Find and update account
        found = False
        for account in accounts_data.get("accounts", []):
            if account.get("account_id") == account_id:
                if "warming_enabled" in body:
                    account.setdefault("warming", {})["enabled"] = bool(body["warming_enabled"])
                if "daily_actions" in body:
                    account.setdefault("warming", {})["daily_actions"] = int(body["daily_actions"])
                if "action_types" in body:
                    account.setdefault("warming", {})["action_types"] = body["action_types"] if isinstance(body["action_types"], list) else [body["action_types"]]
                found = True
                break
        
        if not found:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
        
        # Write back to file
        with open(accounts_path, "w") as f:
            yaml.safe_dump(accounts_data, f, default_flow_style=False, sort_keys=False)
        
        return {"status": "success", "message": "Account config updated"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update account config: {str(e)}")


@router.put("/config/settings")
async def update_settings(request: Request, _auth=Depends(check_auth)):
    """Update app settings"""
    try:
        # Get request body
        body = await request.json()
        
        # Load settings.yaml
        settings_path = Path("config/settings.yaml")
        if not settings_path.exists():
            raise HTTPException(status_code=404, detail="Settings config file not found")
        
        with open(settings_path, "r") as f:
            settings_data = yaml.safe_load(f)
        
        # Update settings
        if "warming_schedule_time" in body:
            settings_data.setdefault("warming", {})["schedule_time"] = body["warming_schedule_time"]
        
        # Write back to file
        with open(settings_path, "w") as f:
            yaml.safe_dump(settings_data, f, default_flow_style=False, sort_keys=False)
        
        return {"status": "success", "message": "Settings updated"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


# File upload endpoint
@router.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    _auth=Depends(check_auth),
):
    """Upload media files and return URLs
    
    Supports two methods:
    1. Cloudinary (recommended) - if CLOUDINARY_* env vars are set
    2. Local server + Cloudflare tunnel (fallback)
    """
    try:
        # Check if Cloudinary is configured
        from .cloudinary_helper import is_cloudinary_configured, upload_to_cloudinary
        use_cloudinary = is_cloudinary_configured()
        
        if use_cloudinary:
            print("DEBUG: Using Cloudinary for file uploads")
        else:
            print("DEBUG: Cloudinary not configured, using local server")
        
        # Create uploads directory if it doesn't exist (for local fallback)
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        uploaded_urls = []
        
        for file in files:
            # Validate file type
            if not file.content_type or not (file.content_type.startswith("image/") or file.content_type.startswith("video/")):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {file.content_type}. Only images and videos are allowed.",
                )
            
            # Generate unique filename
            file_ext = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = upload_dir / unique_filename
            
            # Save file temporarily (always save locally first)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_size = file_path.stat().st_size
            
            # Upload to Cloudinary if configured, otherwise use local server
            if use_cloudinary:
                # Upload to Cloudinary
                print(f"DEBUG: Attempting to upload to Cloudinary...")
                cloudinary_url = upload_to_cloudinary(file_path, public_id=f"instaforge/{unique_filename}")
                
                if cloudinary_url:
                    print(f"DEBUG: Successfully uploaded to Cloudinary: {cloudinary_url}")
                    file_url = cloudinary_url
                else:
                    # Fallback to local server if Cloudinary upload fails
                    print(f"ERROR: Cloudinary upload failed! Check the error messages above.")
                    print(f"ERROR: Falling back to local server (Instagram will likely reject this)")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Cloudinary upload failed. Please check:\n1) Your Cloudinary credentials are correct\n2) You have internet connection\n3) Cloudinary service is available\n\nCheck server logs for detailed error messages."
                    )
            else:
                # Use Cloudflare tunnel URL if available, otherwise use request base URL
                from .cloudflare_helper import get_base_url, get_cloudflare_url
                base_url = get_base_url(str(request.base_url))
                cloudflare_url = get_cloudflare_url()
                
                # Generate file URL
                file_url = f"{base_url}/uploads/{unique_filename}"
                
                print(f"DEBUG: Using local server URL: {file_url}")
                print(f"DEBUG: Cloudflare URL available: {cloudflare_url}")
            
            uploaded_urls.append({
                "url": file_url,
                "originalName": file.filename,
                "size": file_size,
                "type": file.content_type,
            })
        
        return {"urls": uploaded_urls, "count": len(uploaded_urls)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload files: {str(e)}")


# URL verification endpoint (for testing)
@router.get("/test/verify-url")
async def verify_url(request: Request, url: str, _auth=Depends(check_auth)):
    """Test if a URL is accessible and returns correct content type"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/*,video/*,*/*",
        }
        
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        
        content_type = response.headers.get("Content-Type", "")
        content_length = response.headers.get("Content-Length")
        
        is_image = any(ct in content_type.lower() for ct in ["image/", "image/jpeg", "image/png", "image/gif", "image/webp"])
        is_video = any(ct in content_type.lower() for ct in ["video/", "video/mp4", "video/quicktime"])
        
        return {
            "url": url,
            "status_code": response.status_code,
            "content_type": content_type,
            "content_length": content_length,
            "is_valid": response.status_code == 200 and (is_image or is_video),
            "is_image": is_image,
            "is_video": is_video,
            "headers": dict(response.headers),
        }
    except Exception as e:
        return {
            "url": url,
            "error": str(e),
            "is_valid": False,
        }


# System status endpoint
@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request, _auth=Depends(check_auth), app: InstaForgeApp = Depends(get_app)):
    """Get system status"""
    try:
        accounts = app.account_service.list_accounts()
        
        account_list = []
        warming_enabled = False
        
        for account in accounts:
            account_warming_enabled = account.warming.enabled if account.warming else False
            if account_warming_enabled:
                warming_enabled = True
            
            account_list.append({
                "account_id": account.account_id,
                "username": account.username,
                "warming_enabled": account_warming_enabled,
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


# Comment-to-DM Automation endpoints
@router.get("/comment-to-dm/status")
async def get_comment_to_dm_status(
    request: Request,
    account_id: Optional[str] = None,
    _auth=Depends(check_auth),
    app: InstaForgeApp = Depends(get_app),
):
    """Get comment-to-DM automation status for an account"""
    try:
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Comment-to-DM service not initialized")
        
        # Get account ID (use first account if not specified)
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        status_info = app.comment_to_dm_service.get_status(account_id)
        
        return {
            "account_id": account_id,
            "status": status_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/comment-to-dm/config")
async def get_comment_to_dm_config(
    request: Request,
    account_id: Optional[str] = None,
    _auth=Depends(check_auth),
    app: InstaForgeApp = Depends(get_app),
):
    """Get comment-to-DM configuration from accounts.yaml"""
    try:
        # Load accounts config
        config_path = Path("config/accounts.yaml")
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Accounts config file not found")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        accounts = config.get("accounts", [])
        
        # Find account
        if not account_id:
            if accounts:
                account_id = accounts[0].get("account_id")
            else:
                raise HTTPException(status_code=404, detail="No accounts found")
        
        account = next((acc for acc in accounts if acc.get("account_id") == account_id), None)
        if not account:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
        
        comment_to_dm_config = account.get("comment_to_dm", {})
        
        return {
            "account_id": account_id,
            "config": comment_to_dm_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/comment-to-dm/config")
async def update_comment_to_dm_config(
    request: Request,
    account_id: Optional[str] = None,
    _auth=Depends(check_auth),
    app: InstaForgeApp = Depends(get_app),
):
    """Update comment-to-DM configuration in accounts.yaml"""
    try:
        body = await request.json()
        
        # Validate required fields
        enabled = body.get("enabled", False)
        trigger_keyword = body.get("trigger_keyword", "AUTO")
        dm_message_template = body.get("dm_message_template", "")
        link_to_send = body.get("link_to_send", "")
        
        # Load accounts config
        config_path = Path("config/accounts.yaml")
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Accounts config file not found")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        accounts = config.get("accounts", [])
        
        # Find account
        if not account_id:
            if accounts:
                account_id = accounts[0].get("account_id")
            else:
                raise HTTPException(status_code=404, detail="No accounts found")
        
        account = next((acc for acc in accounts if acc.get("account_id") == account_id), None)
        if not account:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
        
        # Update comment_to_dm config
        if "comment_to_dm" not in account:
            account["comment_to_dm"] = {}
        
        account["comment_to_dm"].update({
            "enabled": enabled,
            "trigger_keyword": trigger_keyword or "AUTO",
            "dm_message_template": dm_message_template or "",
            "link_to_send": link_to_send or "",
        })
        
        # Save config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        # Reload accounts in app
        app.accounts = app.config_loader.load_accounts()
        app.account_service = app.account_service.__class__(
            accounts=app.accounts,
            rate_limiter=app.rate_limiter,
            proxy_manager=app.proxy_manager,
        )
        
        return {
            "status": "success",
            "account_id": account_id,
            "config": account["comment_to_dm"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


# Per-post comment-to-DM file management
@router.post("/comment-to-dm/post/{media_id}/file")
async def set_post_dm_file(
    request: Request,
    media_id: str,
    account_id: Optional[str] = None,
    _auth=Depends(check_auth),
    app: InstaForgeApp = Depends(get_app),
):
    """Set file/link to send when someone comments on a specific post"""
    try:
        body = await request.json()
        file_path = body.get("file_path")
        file_url = body.get("file_url")
        
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Comment-to-DM service not initialized")
        
        # Get account ID (use first account if not specified)
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        # Set post-specific file
        app.comment_to_dm_service.post_dm_config.set_post_dm_file(
            account_id=account_id,
            media_id=media_id,
            file_path=file_path,
            file_url=file_url,
        )
        
        return {
            "status": "success",
            "account_id": account_id,
            "media_id": media_id,
            "file_url": file_url or file_path,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set post DM file: {str(e)}")


@router.get("/comment-to-dm/post/{media_id}/file")
async def get_post_dm_file(
    request: Request,
    media_id: str,
    account_id: Optional[str] = None,
    _auth=Depends(check_auth),
    app: InstaForgeApp = Depends(get_app),
):
    """Get file/link configured for a specific post"""
    try:
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Comment-to-DM service not initialized")
        
        # Get account ID (use first account if not specified)
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        file_url = app.comment_to_dm_service.post_dm_config.get_post_dm_file(
            account_id=account_id,
            media_id=media_id,
        )
        
        return {
            "account_id": account_id,
            "media_id": media_id,
            "file_url": file_url,
            "has_file": file_url is not None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get post DM file: {str(e)}")


@router.delete("/comment-to-dm/post/{media_id}/file")
async def remove_post_dm_file(
    request: Request,
    media_id: str,
    account_id: Optional[str] = None,
    _auth=Depends(check_auth),
    app: InstaForgeApp = Depends(get_app),
):
    """Remove file configuration for a post"""
    try:
        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Comment-to-DM service not initialized")
        
        # Get account ID (use first account if not specified)
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        app.comment_to_dm_service.post_dm_config.remove_post_dm_file(
            account_id=account_id,
            media_id=media_id,
        )
        
        return {
            "status": "success",
            "account_id": account_id,
            "media_id": media_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove post DM file: {str(e)}")
