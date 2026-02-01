"""API route handlers for InstaForge web dashboard"""

import json
import yaml
import os
import uuid
import shutil
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Request, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
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
from src.models.account import Account, ProxyConfig, WarmingConfig, CommentToDMConfig, AIDMConfig
from src.app import InstaForgeApp
from src.utils.config import config_manager, Settings
from src.services.scheduled_posts_store import add_scheduled, load_scheduled
from src.services.batch_upload_service import (
    extract_zip,
    validate_file,
    infer_media_type,
    process_batch_upload,
    MAX_FILES_PER_CAMPAIGN,
    SUPPORTED_FORMATS,
)
from src.services.batch_campaign_store import get_campaign, get_all_campaigns
from src.utils.logger import get_logger
from src.auth.meta_oauth import get_meta_login_url, META_APP_ID, META_APP_SECRET, META_REDIRECT_URI
from src.auth.oauth_helper import OAuthHelper
from src.auth.user_auth import hash_password, verify_password, create_session, logout_session
from src.services.user_store import user_store
from src.models.user import User
from web.auth_deps import get_current_user, require_admin, require_auth
from src.auth.user_auth import hash_password, verify_password, create_session, logout_session, validate_session
from src.services.user_store import user_store
from src.models.user import User
from web.auth_deps import get_current_user, require_admin, require_auth
from fastapi.responses import Response

try:
    from .cloudflare_helper import get_cloudflare_url
except ImportError:
    get_cloudflare_url = lambda: None

logger = get_logger(__name__)

# In-memory store for Meta OAuth tokens (temporary)
_meta_token_store: Dict[str, Any] = {}


router = APIRouter(prefix="/api", tags=["api"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])

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


def _is_own_server_url(url: str, request: Request) -> bool:
    """Return True if the URL points to this app's own server (same host as public base URL)."""
    try:
        from .cloudflare_helper import get_base_url
        app_base = get_base_url(str(request.base_url), request.headers if request else None)
        if not app_base:
            return False
        parsed_url = urlparse(url)
        parsed_base = urlparse(app_base)
        url_host = (parsed_url.netloc or "").lower().split(":")[0]
        base_host = (parsed_base.netloc or "").lower().split(":")[0]
        return bool(url_host and base_host and url_host == base_host)
    except Exception:
        return False


@router.get("/health")
async def health_check():
    """Health check endpoint for deployment platforms"""
    return {
        "status": "healthy",
        "service": "instaforge",
        "timestamp": datetime.utcnow().isoformat()
    }


def _fetch_instagram_business_account(user_token: str) -> tuple:
    """
    Call /me/accounts (fields=id,name,access_token,instagram_business_account), get first Page ID
    and page access_token, then /{page_id}?fields=instagram_business_account.
    Returns (page_id, instagram_business_account_id, page_access_token). Raises ValueError if not found.
    Uses Graph API v18.0.
    """
    base = "https://graph.facebook.com/v18.0"
    r = requests.get(
        f"{base}/me/accounts",
        params={
            "access_token": user_token,
            "fields": "id,name,access_token,instagram_business_account",
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        err = data["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise ValueError(f"Failed to load Facebook Pages: {msg}")
    pages = data.get("data", [])
    if not pages:
        raise ValueError("No Facebook Pages found. Create and connect a Page first.")
    first = pages[0]
    page_id = first["id"]
    page_access_token = first.get("access_token")
    if not page_access_token:
        raise ValueError("Page access token not returned.")

    r2 = requests.get(
        f"{base}/{page_id}",
        params={"fields": "instagram_business_account", "access_token": user_token},
        timeout=30,
    )
    data2 = r2.json()
    if "error" in data2:
        err = data2["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise ValueError(f"Failed to load Page details: {msg}")
    ig = data2.get("instagram_business_account")
    if not ig or not ig.get("id"):
        raise ValueError(
            "No Instagram Business account linked to this Page. "
            "Connect an Instagram account to your Page in Meta Business Suite."
        )
    return (page_id, ig["id"], page_access_token)


def _fetch_instagram_username(ig_account_id: str, page_access_token: str) -> str:
    """Fetch username from Instagram Graph API. Returns username or fallback."""
    url = f"https://graph.instagram.com/v18.0/{ig_account_id}"
    r = requests.get(
        url,
        params={"fields": "username", "access_token": page_access_token},
        timeout=30,
    )
    data = r.json()
    if "error" in data or "username" not in data:
        return f"oauth_{ig_account_id}"
    return data["username"]


# --- Meta OAuth ---

def _resolve_redirect_uri() -> str:
    """Use META_REDIRECT_URI when set; else BASE_URL; else Cloudflare tunnel; else env default."""
    # Priority: META_REDIRECT_URI > BASE_URL > Cloudflare tunnel > localhost
    uri = (META_REDIRECT_URI or "").strip()
    if uri and "localhost" not in uri and "127.0.0.1" not in uri:
        return uri
    
    # Check BASE_URL (production domain)
    BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")
    if BASE_URL:
        return f"{BASE_URL}/auth/meta/callback"
    
    # Fallback to Cloudflare tunnel (development)
    base = (get_cloudflare_url() or "").strip().rstrip("/")
    if base:
        return f"{base}/auth/meta/callback"
    
    return uri or "http://localhost:8000/auth/meta/callback"


@auth_router.get("/meta/redirect-uri")
async def auth_meta_redirect_uri():
    """Return the OAuth redirect URI (tunnel or META_REDIRECT_URI). Use this in Meta App settings."""
    return {"redirect_uri": _resolve_redirect_uri()}


@auth_router.get("/meta/login")
async def auth_meta_login():
    """Redirect to Meta OAuth login URL. Uses tunnel or META_REDIRECT_URI."""
    try:
        redirect_uri = _resolve_redirect_uri()
        url = get_meta_login_url(redirect_uri=redirect_uri)
        return RedirectResponse(url=url, status_code=302)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@auth_router.get("/meta/callback")
async def auth_meta_callback(request: Request):
    """
    Meta OAuth callback: read code, exchange for short-lived token,
    exchange for long-lived token, store in memory. Uses Graph API v18.0.
    """
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description", "")

    if error:
        logger.warning("Meta OAuth callback error", error=error, error_description=error_description)
        return HTMLResponse(
            content=f"<html><body><h1>OAuth Error</h1><p>{error}: {error_description}</p></body></html>",
            status_code=400,
        )

    if not code:
        logger.warning("Meta OAuth callback missing code", query=dict(request.query_params))
        return HTMLResponse(
            content="<html><body><h1>Error</h1><p>No code or error received.</p></body></html>",
            status_code=400,
        )

    if not META_APP_ID or not META_APP_SECRET:
        logger.error("Meta OAuth callback: META_APP_ID or META_APP_SECRET not set")
        raise HTTPException(status_code=500, detail="OAuth not configured (missing app credentials)")

    redirect_uri = str(request.url).split("?")[0]
    helper = OAuthHelper(
        app_id=META_APP_ID,
        app_secret=META_APP_SECRET,
        redirect_uri=redirect_uri,
        api_version="v18.0",
    )

    try:
        logger.info("Meta OAuth callback: exchanging code for short-lived token")
        short_lived = await run_in_threadpool(helper.exchange_code_for_token, code)
        access_token_short = short_lived.get("access_token")
        if not access_token_short:
            raise ValueError("Short-lived response missing access_token")
        logger.info("Meta OAuth: short-lived token obtained", expires_in=short_lived.get("expires_in"))

        logger.info("Meta OAuth: exchanging short-lived for long-lived token")
        long_lived = await run_in_threadpool(helper.exchange_for_long_lived_token, access_token_short)
        access_token_long = long_lived.get("access_token")
        expires_in = long_lived.get("expires_in")
        if not access_token_long:
            raise ValueError("Long-lived response missing access_token")
        logger.info("Meta OAuth: long-lived token obtained", expires_in=expires_in)

        logger.info("Meta OAuth: fetching /me/accounts and Instagram Business account")
        try:
            page_id, ig_account_id, page_access_token = await run_in_threadpool(
                _fetch_instagram_business_account, access_token_long
            )
        except ValueError as e:
            logger.warning("Meta OAuth: no connected Instagram account", error=str(e))
            return HTMLResponse(
                content=f"<html><body><h1>Instagram Not Connected</h1><p>{e}</p></body></html>",
                status_code=400,
            )
        logger.info(
            "Meta OAuth: connected Instagram account",
            page_id=page_id,
            instagram_business_account_id=ig_account_id,
        )

        username = await run_in_threadpool(
            _fetch_instagram_username, ig_account_id, page_access_token
        )
        logger.info("Meta OAuth: fetched username", username=username)

        sec = int(expires_in or 0)
        expires_at = (datetime.utcnow() + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")

        oauth_account = Account(
            account_id=ig_account_id,
            username=username,
            access_token=page_access_token,
            expires_at=expires_at,
            instagram_business_id=ig_account_id,
            page_id=page_id,
            user_access_token=access_token_long,
            proxy=ProxyConfig(),
            warming=WarmingConfig(),
            comment_to_dm=CommentToDMConfig(),
        )

        accounts = config_manager.load_accounts()
        seen = {a.account_id for a in accounts}
        if oauth_account.account_id in seen:
            accounts = [a for a in accounts if a.account_id != oauth_account.account_id]
        accounts.append(oauth_account)
        config_manager.save_accounts(accounts)
        logger.info(
            "Meta OAuth: persisted account to accounts.yaml",
            account_id=oauth_account.account_id,
            page_id=page_id,
            instagram_business_id=ig_account_id,
        )

        # Reload accounts so new Meta account is registered everywhere (comment monitor, etc.)
        app = get_app()
        try:
            app.reload_accounts()
            logger.info("Meta OAuth: accounts reloaded, new account registered in all services")
        except Exception as reload_err:
            logger.warning(
                "Meta OAuth: reload_accounts failed (account saved, may need manual reload)",
                error=str(reload_err),
            )
            app.accounts = accounts
            app.account_service.update_accounts(accounts)

        _meta_token_store.clear()
        _meta_token_store.update({
            "access_token": page_access_token,
            "expires_in": expires_in,
            "token_type": long_lived.get("token_type", "unknown"),
            "obtained_at": datetime.utcnow().isoformat() + "Z",
        })
        logger.info("Meta OAuth: token stored in memory", expires_in=expires_in)

        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        logger.exception("Meta OAuth callback: token exchange failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")


# --- User Authentication Endpoints ---

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: Optional[str] = None
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@auth_router.post("/login")
async def login(request: Request, login_data: LoginRequest):
    """Login with username and password"""
    try:
        user = user_store.find_by_username(login_data.username)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive. Please contact an administrator.")
        
        if not verify_password(login_data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Create session
        token = create_session(user.id)
        
        # Create response with cookie
        response = JSONResponse({
            "status": "success",
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "token": token,
        })
        
        # Set cookie (24 hours, httpOnly, secure in production)
        response.set_cookie(
            key="session_token",
            value=token,
            max_age=24 * 60 * 60,  # 24 hours
            httponly=True,
            secure=os.getenv("ENVIRONMENT", "development") == "production",
            samesite="lax",
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@auth_router.post("/logout")
async def logout(request: Request):
    """Logout and clear session"""
    try:
        from web.auth_deps import get_session_token
        token = get_session_token(request)
        
        if token:
            logout_session(token)
        
        response = JSONResponse({"status": "success", "message": "Logged out"})
        response.delete_cookie(key="session_token")
        return response
    except Exception as e:
        logger.exception("Logout error", error=str(e))
        response = JSONResponse({"status": "success", "message": "Logged out"})
        response.delete_cookie(key="session_token")
        return response


@auth_router.post("/register")
async def register(register_data: RegisterRequest):
    """Self-register a new user (creates active account, no approval needed)"""
    try:
        # Validate password length
        if len(register_data.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Check if username already exists
        if user_store.find_by_username(register_data.username):
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Create active user (no admin approval needed)
        import uuid
        new_user = User(
            id=str(uuid.uuid4()),
            username=register_data.username,
            email=register_data.email,
            password_hash=hash_password(register_data.password),
            role="user",
            created_at=datetime.utcnow().isoformat(),
            is_active=True,  # Active immediately, no approval needed
            created_by=None,  # Self-registered
        )
        
        user_store.create_user(new_user)
        
        # Auto-login the user after registration
        token = create_session(new_user.id)
        
        # Create response with cookie (same as login)
        response = JSONResponse({
            "status": "success",
            "message": "Registration successful! You are now logged in.",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role,
            },
            "token": token,
        })
        
        # Set cookie (24 hours, httpOnly, secure in production)
        response.set_cookie(
            key="session_token",
            value=token,
            max_age=24 * 60 * 60,  # 24 hours
            httponly=True,
            secure=os.getenv("ENVIRONMENT", "development") == "production",
            samesite="lax",
        )
        
        return response
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Registration error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@auth_router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
    }


@auth_router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    """Change current user's password"""
    try:
        # Verify current password
        if not verify_password(password_data.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Validate new password
        if len(password_data.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        
        # Update password
        user_store.update_user(current_user.id, password_hash=hash_password(password_data.new_password))
        
        return {"status": "success", "message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Change password error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")


# --- User Management Endpoints (Admin Only) ---

class CreateUserRequest(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    role: str = "user"

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/users")
async def list_users(admin: User = Depends(require_admin)):
    """List all users (admin only)"""
    try:
        users = user_store.load_users()
        return {
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "created_by": user.created_by,
                }
                for user in users
            ]
        }
    except Exception as e:
        logger.exception("List users error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.post("/users")
async def create_user(
    user_data: CreateUserRequest,
    admin: User = Depends(require_admin),
):
    """Create a new user (admin only)"""
    try:
        # Validate password
        if len(user_data.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Validate role
        if user_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        
        # Check if username exists
        if user_store.find_by_username(user_data.username):
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Create user
        import uuid
        new_user = User(
            id=str(uuid.uuid4()),
            username=user_data.username,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            role=user_data.role,
            created_at=datetime.utcnow().isoformat(),
            is_active=True,  # Admin-created users are active by default
            created_by=admin.id,
        )
        
        user_store.create_user(new_user)
        
        return {
            "status": "success",
            "message": "User created successfully",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role,
                "is_active": new_user.is_active,
            },
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Create user error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UpdateUserRequest,
    admin: User = Depends(require_admin),
):
    """Update a user (admin only)"""
    try:
        user = user_store.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent admin from deactivating themselves
        if user_id == admin.id and user_data.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        
        # Prevent changing role of last admin
        if user.role == "admin" and user_data.role == "user":
            users = user_store.load_users()
            active_admins = [u for u in users if u.role == "admin" and u.is_active and u.id != user_id]
            if not active_admins:
                raise HTTPException(status_code=400, detail="Cannot change role of the last active admin")
        
        # Build update dict
        updates = {}
        if user_data.username is not None:
            updates["username"] = user_data.username
        if user_data.email is not None:
            updates["email"] = user_data.email
        if user_data.role is not None:
            if user_data.role not in ["admin", "user"]:
                raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
            updates["role"] = user_data.role
        if user_data.is_active is not None:
            updates["is_active"] = user_data.is_active
        
        updated_user = user_store.update_user(user_id, **updates)
        
        return {
            "status": "success",
            "message": "User updated successfully",
            "user": {
                "id": updated_user.id,
                "username": updated_user.username,
                "email": updated_user.email,
                "role": updated_user.role,
                "is_active": updated_user.is_active,
            },
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Update user error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Delete a user (admin only)"""
    try:
        user = user_store.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent admin from deleting themselves
        if user_id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        user_store.delete_user(user_id)
        
        return {"status": "success", "message": "User deleted successfully"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Delete user error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Activate a user (admin only)"""
    try:
        user = user_store.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        updated_user = user_store.update_user(user_id, is_active=True)
        
        return {
            "status": "success",
            "message": "User activated successfully",
            "user": {
                "id": updated_user.id,
                "username": updated_user.username,
                "is_active": updated_user.is_active,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Activate user error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to activate user: {str(e)}")


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    admin: User = Depends(require_admin),
):
    """Deactivate a user (admin only)"""
    try:
        user = user_store.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent admin from deactivating themselves
        if user_id == admin.id:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        
        updated_user = user_store.update_user(user_id, is_active=False)
        
        return {
            "status": "success",
            "message": "User deactivated successfully",
            "user": {
                "id": updated_user.id,
                "username": updated_user.username,
                "is_active": updated_user.is_active,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Deactivate user error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to deactivate user: {str(e)}")


# --- Account Management Endpoints ---

@router.get("/config/accounts")
async def get_accounts(current_user: User = Depends(require_auth)):
    """List all accounts (filtered by ownership for regular users)"""
    accounts = config_manager.load_accounts()
    
    # Regular users only see their own accounts, admins see all
    if current_user.role != "admin":
        accounts = [acc for acc in accounts if acc.owner_id == current_user.id or acc.owner_id is None]
    
    return {"accounts": [acc.dict() for acc in accounts]}

@router.post("/config/accounts/add")
async def add_account(
    account: Account,
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Add a new account"""
    try:
        accounts = config_manager.load_accounts()
        
        # Check for duplicate ID
        if any(acc.account_id == account.account_id for acc in accounts):
            raise HTTPException(status_code=400, detail=f"Account ID {account.account_id} already exists")
        
        # Set owner_id for regular users (admins can set it explicitly or leave None)
        if current_user.role != "admin":
            account = Account(**{**account.dict(), "owner_id": current_user.id})
        elif account.owner_id is None:
            # Admin can leave owner_id as None to make it visible to all
            pass
            
        accounts.append(account)
        config_manager.save_accounts(accounts)
        
        # Reload app state
        app.accounts = accounts
        app.account_service.update_accounts(accounts)
        
        return {"status": "success", "message": "Account added", "account": account.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add account: {str(e)}")

@router.put("/config/accounts/{account_id}")
async def update_account(
    account_id: str,
    account_update: Account,
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
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
async def delete_account(
    account_id: str,
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Delete an account"""
    try:
        accounts = config_manager.load_accounts()
        
        # Check ownership (regular users can only delete their own accounts)
        found_account = None
        for acc in accounts:
            if acc.account_id == account_id:
                found_account = acc
                break
        
        if not found_account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Regular users can only delete their own accounts
        if current_user.role != "admin" and found_account.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only delete your own accounts")
        
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
async def get_settings(admin: User = Depends(require_admin)):
    """Get global settings (admin only)"""
    settings = config_manager.load_settings()
    return settings.dict()

@router.put("/config/settings")
async def update_settings(
    settings: Settings,
    app: InstaForgeApp = Depends(get_app),
    admin: User = Depends(require_admin),
):
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
async def create_post(
    request: Request,
    post_data: CreatePostRequest,
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Create a new post"""
    try:
        # Keep reels as reels (don't convert to video - Instagram API needs REELS type)
        media_type = post_data.media_type
        
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
            
            # Infer media_type from URL if not explicitly set
            # Handle query parameters (e.g. ?t=timestamp) by checking URL before query
            url0_clean = post_data.urls[0].split("?")[0].split("#")[0].lower()
            if media_type not in ("video", "reels") and url0_clean.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
                # If user selected "image" but URL is video, change to video
                # But if user selected "reels", keep it as reels
                if media_type != "reels":
                    media_type = "video"
                    logger.info("Auto-detected video from URL extension", url=post_data.urls[0])
            
            media = PostMedia(media_type=media_type, url=HttpUrl(post_data.urls[0]), caption=post_data.caption)
        
        # URL validation (always, including scheduled)
        for url in post_data.urls:
            # Same-origin (our uploads): always allow — video/reels from your server
            if _is_own_server_url(url, request):
                continue
            # Non–same-origin: require public HTTPS
            if "localhost" in url or "127.0.0.1" in url or url.startswith("http://"):
                raise HTTPException(status_code=400, detail="Instagram requires public HTTPS URLs.")
            
            # Block unreliable tunnel hosts for video/reels (same-origin already allowed above)
            if media_type in ("video", "reels"):
                unreliable_hosts = ["trycloudflare.com", "ngrok.io", "ngrok-free.app"]
                if any(host in url.lower() for host in unreliable_hosts):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                                f"{media_type.capitalize()} posts: Use “Upload Media” to upload from your device — the file is stored on your server and published to Instagram. Set BASE_URL in production."
                        )
                    )
                
                # Pre-flight validation for video/reels URLs (test before posting)
                try:
                    import requests
                    headers = {
                        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                        "Accept": "video/*,*/*",
                    }
                    test_response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
                    
                    if test_response.status_code != 200:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"{media_type.capitalize()} URL returned status {test_response.status_code}. "
                                f"Use “Upload Media” to upload from your device instead — the file is stored on your server and published to Instagram."
                            )
                        )
                    
                    content_type = test_response.headers.get("Content-Type", "").lower()
                    if "text/html" in content_type:
                        # Try GET to see what we're getting
                        try:
                            get_response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
                            error_preview = get_response.text[:200] if get_response.text else ""
                            raise HTTPException(
                                status_code=400,
                                detail=(
                                    f"{media_type.capitalize()} URL returns a page instead of a video file. "
                                    f"Use “Upload Media” to upload from your device — the file is stored on your server and published to Instagram."
                                )
                            )
                        except HTTPException:
                            raise
                        except Exception:
                            pass
                    
                    if not any(ct in content_type for ct in ["video/", "application/octet-stream"]):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"⚠️ {media_type.capitalize()} URL has wrong Content-Type:\n\n"
                                f"URL: {url}\n"
                                f"Content-Type: {content_type}\n\n"
                                f"Expected: video/mp4, video/quicktime, or application/octet-stream\n"
                                f"Got: {content_type}\n\n"
                                f"Instagram may not accept this URL. Use a direct video file URL."
                            )
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    # If validation fails but it's not a clear error, log and continue
                    # Instagram will verify anyway and return a clear error
                    logger.warning(
                        "URL validation had issues, continuing - Instagram will verify",
                        url=url,
                        error=str(e),
                    )

        is_scheduled = post_data.scheduled_time is not None

        if is_scheduled:
            # Persist scheduled post; publish later via background job
            # Include Auto-DM config so it can be applied after publishing
            sid = add_scheduled(
                account_id=post_data.account_id,
                media_type=media_type,
                urls=post_data.urls,
                caption=post_data.caption or "",
                scheduled_time=post_data.scheduled_time,
                hashtags=post_data.hashtags,
                auto_dm_enabled=post_data.auto_dm_enabled or False,
                auto_dm_link=post_data.auto_dm_link,
                auto_dm_mode=post_data.auto_dm_mode or "AUTO",
                auto_dm_trigger=post_data.auto_dm_trigger,
                auto_dm_ai_enabled=post_data.auto_dm_ai_enabled or False,
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
            
            # Save Auto-DM config for immediate posts (if enabled)
            if post_data.auto_dm_enabled and post_data.auto_dm_link and post.instagram_media_id:
                try:
                    if app.comment_to_dm_service:
                        app.comment_to_dm_service.post_dm_config.set_post_dm_file(
                            account_id=post_data.account_id,
                            media_id=str(post.instagram_media_id),
                            file_url=post_data.auto_dm_link,
                            trigger_mode=post_data.auto_dm_mode or "AUTO",
                            trigger_word=post_data.auto_dm_trigger,
                            ai_enabled=post_data.auto_dm_ai_enabled or False,
                        )
                        logger.info(
                            "Auto-DM config saved for immediate post",
                            account_id=post_data.account_id,
                            media_id=str(post.instagram_media_id),
                        )
                except Exception as dm_err:
                    logger.warning(
                        "Failed to save Auto-DM config for immediate post",
                        account_id=post_data.account_id,
                        error=str(dm_err),
                    )
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


@router.get("/schedule/queue")
async def get_schedule_queue(
    current_user: User = Depends(require_auth),
):
    """Get scheduling queue (upcoming scheduled posts) and failed posts with error reason."""
    try:
        posts = load_scheduled()
        queue = []
        failed = []
        for p in posts:
            item = {
                "id": p.get("id"),
                "account_id": p.get("account_id"),
                "scheduled_time": p.get("scheduled_time"),
                "media_type": p.get("media_type"),
                "caption": (p.get("caption") or "")[:200],
                "urls": p.get("urls") or [],
                "created_at": p.get("created_at"),
            }
            status = (p.get("status") or "scheduled").lower()
            if status == "failed":
                item["error_message"] = p.get("error_message") or "Unknown error"
                item["failed_at"] = p.get("failed_at")
                failed.append(item)
            else:
                queue.append(item)
        # Sort queue by scheduled_time ascending; failed by failed_at descending
        queue.sort(key=lambda x: (x["scheduled_time"] or ""))
        failed.sort(key=lambda x: (x.get("failed_at") or ""), reverse=True)
        return {
            "status": "success",
            "queue": queue,
            "failed": failed,
            "queue_count": len(queue),
            "failed_count": len(failed),
        }
    except Exception as e:
        logger.exception("Failed to get schedule queue", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get schedule queue: {str(e)}")


# --- Status & Utils ---

@router.get("/status", response_model=StatusResponse)
async def get_status(
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
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


@router.post("/warming/run")
async def run_warming_now(
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Manually trigger warming actions for all accounts"""
    try:
        logger.info("Manual warming trigger requested")
        # Run in thread pool so long-running warming (browser/API) doesn't block the event loop
        results = await run_in_threadpool(app.run_warming_now)
        
        return {
            "status": "success",
            "message": "Warming actions executed",
            "results": results,
        }
    except Exception as e:
        logger.exception("Failed to run warming", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to run warming: {str(e)}")


@router.get("/warming/status")
async def get_warming_status(
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Get warming status for all accounts"""
    try:
        accounts = app.account_service.list_accounts()
        
        warming_status = []
        for account in accounts:
            warming_config = account.warming if account.warming else None
            warming_status.append({
                "account_id": account.account_id,
                "username": account.username,
                "enabled": warming_config.enabled if warming_config else False,
                "daily_actions": warming_config.daily_actions if warming_config else 0,
                "action_types": warming_config.action_types if warming_config else [],
            })
        
        schedule_time = app.config.warming.schedule_time if app.config else "09:00"
        
        return {
            "status": "success",
            "schedule_time": schedule_time,
            "accounts": warming_status,
        }
    except Exception as e:
        logger.exception("Failed to get warming status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get warming status: {str(e)}")

@router.post("/upload")
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    """Upload media files"""
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        uploaded_urls = []
        from .cloudflare_helper import get_base_url
        base_url = get_base_url(str(request.base_url), request.headers if request else None)
        
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

@router.post("/batch/upload")
async def batch_upload(
    request: Request,
    account_id: str = Form(...),
    start_date: str = Form(...),
    end_date: Optional[str] = Form(None),
    caption: str = Form(""),
    files: Optional[List[UploadFile]] = File(None),
    zip_file: Optional[UploadFile] = File(None),
):
    """
    Upload and schedule multiple media files as a 30-day batch campaign.
    Accepts either multiple files OR a ZIP file.
    """
    try:
        from .cloudflare_helper import get_base_url
        base_url = get_base_url(str(request.base_url), request.headers if request else None)
        
        # Parse start_date
        try:
            start_date_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            # Convert to naive datetime (remove timezone)
            if start_date_dt.tzinfo:
                start_date_dt = start_date_dt.replace(tzinfo=None)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid start_date format: {str(e)}")
        
        # Parse end_date (optional)
        end_date_dt = None
        if end_date:
            try:
                end_date_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                # Convert to naive datetime (remove timezone)
                if end_date_dt.tzinfo:
                    end_date_dt = end_date_dt.replace(tzinfo=None)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end_date format: {str(e)}")
        
        # Parse hashtags from form data (can be multiple entries with same key)
        form_data = await request.form()
        hashtags_list = form_data.getlist("hashtags")
        hashtags = [h for h in hashtags_list if h.strip()] if hashtags_list else None
        
        # Validate input
        if not files and not zip_file:
            raise HTTPException(status_code=400, detail="Either files or zip_file must be provided")
        
        if files and zip_file:
            raise HTTPException(status_code=400, detail="Provide either files OR zip_file, not both")
        
        # Prepare upload directory for campaign
        campaign_upload_dir = Path("uploads") / "batch"
        campaign_upload_dir.mkdir(parents=True, exist_ok=True)
        
        valid_files = []
        
        if zip_file:
            # Handle ZIP upload
            if not zip_file.filename or not zip_file.filename.lower().endswith('.zip'):
                raise HTTPException(status_code=400, detail="ZIP file must have .zip extension")
            
            # Save ZIP temporarily
            temp_zip_path = campaign_upload_dir / f"temp_{uuid.uuid4()}.zip"
            with open(temp_zip_path, "wb") as buffer:
                shutil.copyfileobj(zip_file.file, buffer)
            
            # Extract ZIP
            extract_dir = campaign_upload_dir / f"extract_{uuid.uuid4()}"
            extract_dir.mkdir(exist_ok=True)
            
            try:
                extracted_files = extract_zip(temp_zip_path, extract_dir)
                
                # Move extracted files to campaign directory (will be organized by campaign_id later)
                for extracted_file in extracted_files:
                    # Keep files in extract_dir for now, will move to campaign folder after campaign creation
                    valid_files.append(extracted_file)
                
                # Clean up temp ZIP
                temp_zip_path.unlink()
            
            except ValueError as e:
                # Clean up on error
                if temp_zip_path.exists():
                    temp_zip_path.unlink()
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                raise HTTPException(status_code=400, detail=str(e))
        
        else:
            # Handle multiple file uploads
            if len(files) > MAX_FILES_PER_CAMPAIGN:
                raise HTTPException(
                    status_code=400,
                    detail=f"Too many files: {len(files)} (max {MAX_FILES_PER_CAMPAIGN})"
                )
            
            # Validate and save files
            for file in files:
                if not file.filename:
                    continue
                
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in SUPPORTED_FORMATS:
                    logger.warning("Skipping unsupported file", filename=file.filename, ext=file_ext)
                    continue
                
                # Save file
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_path = campaign_upload_dir / unique_filename
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Validate saved file
                is_valid, error = validate_file(file_path)
                if is_valid:
                    valid_files.append(file_path)
                else:
                    logger.warning("Invalid file skipped", filename=file.filename, error=error)
                    if file_path.exists():
                        file_path.unlink()
        
        if len(valid_files) == 0:
            raise HTTPException(status_code=400, detail="No valid files found after validation")
        
        if len(valid_files) > MAX_FILES_PER_CAMPAIGN:
            # Clean up files
            for f in valid_files:
                if f.exists():
                    f.unlink()
            raise HTTPException(
                status_code=400,
                detail=f"Too many valid files: {len(valid_files)} (max {MAX_FILES_PER_CAMPAIGN})"
            )
        
        # Create campaign and organize files
        campaign_id = str(uuid.uuid4())
        campaign_dir = campaign_upload_dir / campaign_id
        campaign_dir.mkdir(exist_ok=True)
        
        # Move files to campaign directory and rename for clarity
        organized_files = []
        for idx, file_path in enumerate(valid_files):
            file_ext = file_path.suffix
            new_name = f"day_{idx:02d}{file_ext}"
            new_path = campaign_dir / new_name
            
            # Move file
            if file_path != new_path:
                shutil.move(str(file_path), str(new_path))
            organized_files.append(new_path)
        
        # Clean up extract directory if it exists
        extract_parent = campaign_upload_dir / f"extract_{uuid.uuid4().hex[:8]}"
        for extract_dir in campaign_upload_dir.glob("extract_*"):
            if extract_dir.is_dir() and not any(extract_dir.iterdir()):
                try:
                    extract_dir.rmdir()
                except OSError:
                    pass
        
        # Process batch upload (create campaign and schedule posts)
        result = await run_in_threadpool(
            process_batch_upload,
            account_id=account_id,
            files=organized_files,
            start_date=start_date_dt,
            end_date=end_date_dt,
            caption=caption,
            hashtags=hashtags,
            base_url=base_url,
        )
        
        # Update campaign with actual campaign_id from result
        campaign_id = result["campaign_id"]
        
        logger.info(
            "Batch upload completed",
            campaign_id=campaign_id,
            scheduled_count=result["scheduled_count"],
            total_files=result["total_files"],
            errors_count=len(result["errors"]),
        )
        
        return {
            "status": "success",
            "campaign_id": campaign_id,
            "scheduled_count": result["scheduled_count"],
            "total_files": result["total_files"],
            "errors": result["errors"],
            "message": f"Scheduled {result['scheduled_count']} posts starting from {start_date_dt.isoformat()}",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Batch upload failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")

@router.get("/batch/campaigns")
async def get_batch_campaigns(account_id: Optional[str] = None):
    """Get all batch campaigns, optionally filtered by account_id."""
    try:
        campaigns = get_all_campaigns(account_id=account_id)
        return {"campaigns": campaigns, "count": len(campaigns)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get campaigns: {str(e)}")

@router.get("/batch/campaigns/{campaign_id}")
async def get_batch_campaign(campaign_id: str):
    """Get a specific batch campaign by ID."""
    try:
        campaign = get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return {"campaign": campaign}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get campaign: {str(e)}")

@router.get("/test/verify-url")
async def verify_url(url: str):
    """Test URL accessibility with Instagram's user agent"""
    try:
        # Test with Instagram's actual user agent
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "image/*,video/*,*/*",
        }
        response = await run_in_threadpool(requests.head, url, headers=headers, timeout=10, allow_redirects=True)
        
        content_type = response.headers.get("Content-Type", "")
        is_image = any(ct in content_type.lower() for ct in ["image/jpeg", "image/png", "image/gif", "image/webp"])
        is_video = any(ct in content_type.lower() for ct in ["video/mp4", "video/quicktime"])
        is_html = "text/html" in content_type.lower()
        
        # If HTML, try to get a snippet to see what error we're getting
        error_preview = None
        if is_html or response.status_code != 200:
            try:
                get_response = await run_in_threadpool(requests.get, url, headers=headers, timeout=5, allow_redirects=True)
                error_preview = get_response.text[:200] if get_response.text else None
            except Exception:
                pass
        
        return {
            "url": url,
            "status_code": response.status_code,
            "content_type": content_type,
            "content_length": response.headers.get("Content-Length"),
            "is_valid": response.status_code == 200 and (is_image or is_video),
            "is_image": is_image,
            "is_video": is_video,
            "is_html": is_html,
            "error_preview": error_preview,
            "warning": "URL returns HTML instead of media" if is_html else None,
            "all_headers": dict(response.headers),
        }
    except Exception as e:
        return {"url": url, "error": str(e), "is_valid": False}

@router.get("/test/check-file")
async def check_file(filename: str):
    """Check if a file exists in uploads directory"""
    from pathlib import Path
    import os
    
    # Get absolute path to uploads directory (works from any working directory)
    base_dir = Path(__file__).parent.parent  # Go up from web/ to project root
    uploads_path = base_dir / "uploads"
    file_path = uploads_path / filename
    
    try:
        if not file_path.exists():
            return {
                "filename": filename,
                "exists": False,
                "error": "File not found",
                "path": str(file_path),
            }
        
        if not file_path.is_file():
            return {
                "filename": filename,
                "exists": False,
                "error": "Path is not a file",
                "path": str(file_path),
            }
        
        file_size = file_path.stat().st_size
        ext = file_path.suffix.lower()
        
        return {
            "filename": filename,
            "exists": True,
            "size": file_size,
            "extension": ext,
            "path": str(file_path),
            "readable": os.access(file_path, os.R_OK),
        }
    except Exception as e:
        return {
            "filename": filename,
            "exists": False,
            "error": str(e),
        }


@router.post("/test/ai-reply")
async def test_ai_reply(
    message: str = Form(...),
    account_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form("test_user_123"),
    app: InstaForgeApp = Depends(get_app),
):
    """
    Test endpoint for AI DM auto-reply feature.
    
    Args:
        message: Test message to send to AI
        account_id: Optional account ID (uses first account if not provided)
        user_id: Optional user ID for testing (defaults to test_user_123)
        
    Returns:
        AI-generated reply or error message
    """
    try:
        from src.features.ai_dm import AIDMHandler
        
        # Get account ID
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id
        
        # Get account username
        account = app.account_service.get_account(account_id)
        account_username = account.username if account else None
        
        # Check AI DM config
        ai_dm_enabled = False
        if account and hasattr(account, 'ai_dm') and account.ai_dm:
            ai_dm_enabled = account.ai_dm.enabled
        
        # Initialize handler
        ai_handler = AIDMHandler()
        
        if not ai_handler.is_available():
            return {
                "status": "error",
                "error": "OpenAI API not configured. Set OPENAI_API_KEY in .env",
                "reply": None,
                "ai_dm_enabled": ai_dm_enabled,
            }
        
        # Generate reply using process_incoming_dm (simulates webhook flow)
        result = ai_handler.process_incoming_dm(
            account_id=account_id,
            user_id=user_id or "test_user_123",
            message_text=message,
            message_id=None,
            account_username=account_username,
        )
        
        return {
            "status": "success",
            "message": message,
            "reply_text": result.get("reply_text"),
            "reply_status": result.get("status"),
            "reason": result.get("reason"),
            "account_id": account_id,
            "user_id": user_id,
            "account_username": account_username,
            "ai_dm_enabled": ai_dm_enabled,
        }
    except Exception as e:
        logger.exception("AI reply test failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "reply": None,
        }


@router.get("/ai/profile")
async def get_ai_profile(
    account_id: Optional[str] = None,
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Get AI profile for an account"""
    try:
        from src.features.ai_brain import AISettingsService
        
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                return {
                    "status": "error",
                    "error": "No accounts configured",
                    "account_id": None,
                    "profile": None,
                }
            account_id = accounts[0].account_id
        
        ai_service = AISettingsService()
        profile = ai_service.get_profile(account_id)
        
        return {
            "status": "success",
            "account_id": account_id,
            "profile": profile,
        }
    except ImportError as e:
        logger.error("AI Brain module not available", error=str(e))
        return {
            "status": "error",
            "error": "AI Brain module not available. Please ensure all dependencies are installed.",
            "account_id": account_id,
            "profile": None,
        }
    except Exception as e:
        logger.exception("Failed to get AI profile", error=str(e))
        return {
            "status": "error",
            "error": f"Failed to get AI profile: {str(e)}",
            "account_id": account_id,
            "profile": None,
        }


@router.post("/ai/profile/update")
async def update_ai_profile(
    account_id: Optional[str] = Form(None),
    current_user: User = Depends(require_auth),
    brand_name: Optional[str] = Form(None),
    business_type: Optional[str] = Form(None),
    tone: Optional[str] = Form(None),
    custom_tone: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    pricing: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    about_business: Optional[str] = Form(None),
    custom_rules: Optional[str] = Form(None),
    custom_prompt: Optional[str] = Form(None),
    enable_memory: Optional[bool] = Form(None),
    app: InstaForgeApp = Depends(get_app),
):
    """Update AI profile for an account"""
    try:
        from src.features.ai_brain import AISettingsService
        
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                return {
                    "status": "error",
                    "error": "No accounts configured",
                    "account_id": None,
                    "profile": None,
                }
            account_id = accounts[0].account_id
        
        ai_service = AISettingsService()
        
        # Build update data
        update_data = {}
        if brand_name is not None:
            update_data["brand_name"] = brand_name
        if business_type is not None:
            update_data["business_type"] = business_type
        if tone is not None:
            update_data["tone"] = tone
        if custom_tone is not None:
            update_data["custom_tone"] = custom_tone
        if language is not None:
            update_data["language"] = language
        if pricing is not None:
            update_data["pricing"] = pricing
        if location is not None:
            update_data["location"] = location
        if about_business is not None:
            update_data["about_business"] = about_business
        if custom_rules is not None:
            # Parse custom rules (comma-separated or newline-separated)
            rules = [r.strip() for r in custom_rules.replace("\n", ",").split(",") if r.strip()]
            update_data["custom_rules"] = rules
        if custom_prompt is not None:
            update_data["custom_prompt"] = custom_prompt
        if enable_memory is not None:
            update_data["enable_memory"] = enable_memory
        
        profile = ai_service.update_profile(account_id, update_data)
        
        return {
            "status": "success",
            "account_id": account_id,
            "profile": profile,
        }
    except ImportError as e:
        logger.error("AI Brain module not available", error=str(e))
        return {
            "status": "error",
            "error": "AI Brain module not available. Please ensure all dependencies are installed.",
            "account_id": account_id,
            "profile": None,
        }
    except Exception as e:
        logger.exception("Failed to update AI profile", error=str(e))
        return {
            "status": "error",
            "error": f"Failed to update AI profile: {str(e)}",
            "account_id": account_id,
            "profile": None,
        }


@router.get("/ai/memory/stats")
async def get_ai_memory_stats(
    account_id: Optional[str] = None,
    app: InstaForgeApp = Depends(get_app),
):
    """Get AI memory statistics for an account"""
    try:
        from src.features.ai_brain import AISettingsService
        
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                return {
                    "status": "error",
                    "error": "No accounts configured",
                    "account_id": None,
                    "stats": None,
                }
            account_id = accounts[0].account_id
        
        ai_service = AISettingsService()
        stats = ai_service.get_memory_stats(account_id)
        
        return {
            "status": "success",
            "account_id": account_id,
            "stats": stats,
        }
    except ImportError as e:
        logger.error("AI Brain module not available", error=str(e))
        return {
            "status": "success",
            "account_id": account_id,
            "stats": {
                "total_users": 0,
                "total_messages": 0,
                "users_with_tags": 0,
            },
        }
    except Exception as e:
        logger.exception("Failed to get AI memory stats", error=str(e))
        return {
            "status": "success",
            "account_id": account_id,
            "stats": {
                "total_users": 0,
                "total_messages": 0,
                "users_with_tags": 0,
            },
        }


@router.post("/ai/memory/reset")
async def reset_ai_memory(
    account_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    app: InstaForgeApp = Depends(get_app),
):
    """Reset AI memory for an account or specific user"""
    try:
        from src.features.ai_brain import AISettingsService
        
        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                return {
                    "status": "error",
                    "error": "No accounts configured",
                    "account_id": None,
                    "user_id": user_id,
                }
            account_id = accounts[0].account_id
        
        ai_service = AISettingsService()
        success = ai_service.reset_memory(account_id, user_id)
        
        if not success:
            return {
                "status": "error",
                "error": "Memory not found",
                "account_id": account_id,
                "user_id": user_id,
            }
        
        return {
            "status": "success",
            "account_id": account_id,
            "user_id": user_id,
            "message": "Memory reset successfully",
        }
    except ImportError as e:
        logger.error("AI Brain module not available", error=str(e))
        return {
            "status": "error",
            "error": "AI Brain module not available",
            "account_id": account_id,
            "user_id": user_id,
        }
    except Exception as e:
        logger.exception("Failed to reset AI memory", error=str(e))
        return {
            "status": "error",
            "error": f"Failed to reset AI memory: {str(e)}",
            "account_id": account_id,
            "user_id": user_id,
        }


@router.get("/test/ai-dm-status")
async def test_ai_dm_status(app: InstaForgeApp = Depends(get_app)):
    """
    Diagnostic endpoint to check AI DM configuration and webhook setup.
    
    Returns:
        Status of AI DM feature for all accounts
    """
    try:
        from src.features.ai_dm import AIDMHandler
        
        accounts = app.account_service.list_accounts()
        ai_handler = AIDMHandler()
        
        status = {
            "openai_configured": ai_handler.is_available(),
            "accounts": [],
        }
        
        for account in accounts:
            ai_dm_enabled = False
            if hasattr(account, 'ai_dm') and account.ai_dm:
                ai_dm_enabled = account.ai_dm.enabled
            
            account_status = {
                "account_id": account.account_id,
                "username": account.username,
                "ai_dm_enabled": ai_dm_enabled,
                "instagram_business_id": getattr(account, 'instagram_business_id', None),
                "has_ai_dm_config": hasattr(account, 'ai_dm') and account.ai_dm is not None,
            }
            status["accounts"].append(account_status)
        
        return status
    except Exception as e:
        logger.exception("AI DM status check failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/webhooks/callback-url")
async def get_webhook_callback_url():
    """
    Return the Instagram webhook configuration for Meta app.
    In Meta app: set Callback URL to production_url (e.g. https://veilforce.com/webhooks/instagram).
    Do NOT use this /api/webhooks/callback-url path as the Callback URL in Meta.
    """
    from .cloudflare_helper import get_cloudflare_url
    verify_token = os.environ.get("WEBHOOK_VERIFY_TOKEN", "my_test_token_for_instagram_verification")
    
    BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")
    if BASE_URL:
        callback_url = f"{BASE_URL}/webhooks/instagram"
        production_url = callback_url
    else:
        base = get_cloudflare_url()
        if base:
            callback_url = f"{base.rstrip('/')}/webhooks/instagram"
        else:
            callback_url = None
        production_url = "https://veilforce.com/webhooks/instagram"
    
    return {
        "callback_url": callback_url or production_url,
        "verify_token": verify_token,
        "production_url": production_url,
        "meta_callback_url": production_url,
        "note": "In Meta app: set Callback URL to production_url; set Verify token to verify_token above. On veilforce.com server set BASE_URL=https://veilforce.com. Do NOT use /api/webhooks/callback-url as Callback URL.",
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
        ai_enabled = body.get("ai_enabled", False)

        if not file_url and not file_path:
            raise HTTPException(status_code=400, detail="File URL or path required")

        if not app.comment_to_dm_service:
            raise HTTPException(status_code=500, detail="Service not initialized")

        if not account_id:
            accounts = app.account_service.list_accounts()
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts configured")
            account_id = accounts[0].account_id

        logger.info(
            "Saving post DM config",
            account_id=account_id,
            media_id=media_id,
            file_url=file_url,
            trigger_mode=trigger_mode,
            trigger_word=trigger_word,
            ai_enabled=ai_enabled,
        )

        app.comment_to_dm_service.post_dm_config.set_post_dm_file(
            account_id=account_id,
            media_id=media_id,
            file_path=file_path,
            file_url=file_url,
            trigger_mode=trigger_mode,
            trigger_word=trigger_word,
            ai_enabled=ai_enabled,
        )

        saved_config = app.comment_to_dm_service.post_dm_config.get_post_dm_config(account_id, media_id)
        logger.info(
            "Post DM config saved and verified",
            account_id=account_id,
            media_id=media_id,
            saved_file_url=saved_config.get("file_url") if saved_config else None,
        )

        return {
            "status": "success",
            "account_id": account_id,
            "media_id": media_id,
            "file_url": file_url or file_path,
            "trigger_mode": trigger_mode,
            "trigger_word": trigger_word,
            "ai_enabled": saved_config.get("ai_enabled", False) if saved_config else ai_enabled,
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
                "ai_enabled": config.get("ai_enabled", False),
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


# Account Management Endpoints

@router.get("/accounts/status")
async def get_accounts_status(
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Get health status for all accounts"""
    try:
        if not app.account_health_service:
            raise HTTPException(status_code=500, detail="Health service not initialized")
        
        # Run blocking health checks in thread pool so the async event loop doesn't block
        results = await run_in_threadpool(app.account_health_service.check_all_accounts)
        
        # Format response
        status_list = []
        for account_id, result in results.items():
            try:
                account = app.account_service.get_account(account_id)
                status_list.append({
                    "account_id": account_id,
                    "username": account.username,
                    "status": result.status.value,
                    "checks": result.checks,
                    "timestamp": result.timestamp.isoformat(),
                })
            except Exception as e:
                logger.warning("Failed to get account info for status", account_id=account_id, error=str(e))
                status_list.append({
                    "account_id": account_id,
                    "username": "Unknown",
                    "status": result.status.value,
                    "checks": result.checks,
                    "timestamp": result.timestamp.isoformat(),
                })
        
        return {
            "status": "success",
            "accounts": status_list,
            "total": len(status_list),
        }
    except Exception as e:
        logger.exception("Failed to get account status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get account status: {str(e)}")


@router.get("/accounts/{account_id}/status")
async def get_account_status(account_id: str, app: InstaForgeApp = Depends(get_app)):
    """Get health status for a specific account"""
    try:
        if not app.account_health_service:
            raise HTTPException(status_code=500, detail="Health service not initialized")
        
        # Check health for this account
        result = app.account_health_service.check_account_health(account_id)
        
        try:
            account = app.account_service.get_account(account_id)
            username = account.username
        except Exception:
            username = "Unknown"
        
        return {
            "status": "success",
            "account_id": account_id,
            "username": username,
            "health_status": result.status.value,
            "checks": result.checks,
            "timestamp": result.timestamp.isoformat(),
        }
    except Exception as e:
        logger.exception("Failed to get account status", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get account status: {str(e)}")


@router.post("/accounts/{account_id}/onboard")
async def onboard_account(account_id: str, app: InstaForgeApp = Depends(get_app)):
    """Onboard a specific account through the onboarding pipeline"""
    try:
        if not app.account_onboarding_service:
            raise HTTPException(status_code=500, detail="Onboarding service not initialized")
        
        # Get account
        account = app.account_service.get_account(account_id)
        
        # Run onboarding
        result = app.account_onboarding_service.onboard_account(account, app_instance=app)
        
        return {
            "status": "success",
            "onboarding_result": result.to_dict(),
        }
    except Exception as e:
        logger.exception("Failed to onboard account", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to onboard account: {str(e)}")


@router.post("/accounts/reload")
async def reload_accounts(
    app: InstaForgeApp = Depends(get_app),
    current_user: User = Depends(require_auth),
):
    """Reload accounts from config and re-register in all services"""
    try:
        results = app.reload_accounts()
        
        return {
            "status": "success",
            "results": results,
        }
    except Exception as e:
        logger.exception("Failed to reload accounts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reload accounts: {str(e)}")
