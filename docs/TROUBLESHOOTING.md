# Troubleshooting Guide

## Common Issues and Fixes

### Port 8000 Already in Use

If you see:
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

**Fix:**
1. Run `scripts/stop_server.ps1` to kill existing Python processes
2. Or set a different port: `$env:WEB_PORT = "8001"`
3. Or find and kill the specific process: `netstat -ano | findstr :8000`, then `taskkill /PID <PID> /F`

### Invalid App ID Error (Error Code 190)

**Problem:** App ID and App Secret don't match.

**Fix:**
1. Get correct credentials from https://developers.facebook.com/apps/YOUR_APP_ID/settings/basic/
2. Update `config/app_credentials.yaml` with exact App ID and Secret (with quotes)
3. Ensure Instagram Graph API product is added to your app
4. Verify OAuth Redirect URI is set: `http://localhost:8080/`

### Cloudinary Invalid Signature Error

**Problem:** API Secret is incorrect.

**Fix:**
1. Go to https://cloudinary.com/console → Dashboard
2. Copy the correct API Secret (click "Reveal")
3. Update `.env` file with exact secret (no quotes, no spaces)
4. Restart server

### Server Won't Start

- Check if port is in use (see above)
- Verify Python dependencies: `pip install -r requirements.txt`
- Check logs in `logs/instaforge.log`

### Instagram API Errors

- **Error 9004 (Media Type)**: Use Cloudinary for media uploads, not Cloudflare tunnels
- **Rate Limit Errors**: Reduce request frequency in `config/settings.yaml`
- **Token Expired**: Regenerate token using `scripts/generate_token.py`

## Getting Help

- Check logs: `logs/instaforge.log`
- Review configuration: `config/accounts.yaml`, `config/settings.yaml`
- See setup guides: `docs/SETUP.md`, `docs/CLOUDINARY.md`
# Troubleshooting: No Auto-Reply or Auto-DM Working

## Problem
- Someone commented on your post
- No reply was sent
- No automatic DM was sent

## Root Causes Identified

### 1. ✅ FIXED: Comment-to-DM is Now Enabled
**Status**: Now enabled in `config/accounts.yaml` (`enabled: true`)

### 2. ⚠️ CRITICAL: Instagram API Can't Read Comments
**Problem**: Instagram Graph API is returning **0 comments** even though comments exist.

**Evidence from logs**:
```
"comment_count": 0, "response_keys": ["data", "paging"]
"processed": 0, "replied": 0, "skipped": 0, "failed": 0
```

**Why This Happens**:
- Instagram Graph API requires **specific permissions** to read comments
- Your access token may not have `instagram_manage_comments` permission
- Even with permissions, Instagram API has limitations

## Solutions

### Solution 1: Fix Instagram API Permissions (Recommended)

1. **Regenerate your access token** with correct permissions:
   - Go to: https://developers.facebook.com/tools/explorer/
   - Select your app
   - Get token with permissions:
     - ✅ `instagram_basic`
     - ✅ `instagram_manage_comments` (REQUIRED for reading comments)
     - ✅ `instagram_manage_messages` (REQUIRED for sending DMs)
     - ✅ `instagram_content_publish`

2. **Update `config/accounts.yaml`** with new token:
   ```yaml
   access_token: "YOUR_NEW_TOKEN_HERE"
   ```

3. **Restart server**: `python web_server.py`

### Solution 2: Use Post-Specific File Attachment (Works Even Without Comments API)

Since we added per-post file attachment, you can:

1. **Go to Published Posts page** (http://localhost:8000/posts)
2. **Click "📎 Attach File"** on the post that has comments
3. **Enter your file**: `C:/Users/kanis/Downloads/2508843519.pdf`
4. **Save**

**How This Works**:
- Even if API can't read comments, when it eventually detects them (once permissions are fixed), the system will send the attached file
- The file is stored and ready to send as soon as comments are detected

### Solution 3: Check if Comments Are Actually Visible

**Test manually**:
1. Go to Instagram and check if you can see the comment
2. If you can see it but API returns 0, it's a permissions issue
3. If you can't see it, the comment may have been deleted/hidden

## Current Configuration Status

After fixes:
- ✅ Comment-to-DM: **ENABLED** (`enabled: true`)
- ✅ Auto-reply: **ENABLED** (always on)
- ✅ Monitoring: **RUNNING** (checks every 60 seconds)
- ⚠️ API Permissions: **NEEDS FIX** (can't read comments)

## What to Do Now

1. **Enable automation** (DONE - I just enabled it)
2. **Fix API permissions** - Get new token with `instagram_manage_comments` permission
3. **Restart server** after updating token
4. **Check logs** - Look for "Found comments to process" messages

## Testing

After fixing permissions:

1. Restart server
2. Wait 60 seconds for next check cycle
3. Check logs: `logs/instaforge.log`
4. Look for:
   - `"Found comments to process for auto-DM"`
   - `"DM sent successfully"`
   - `"Comment-to-DM automation processed comments"`

## Expected Behavior When Working

When someone comments:
1. ✅ System detects comment (within 60 seconds)
2. ✅ Auto-reply sent (if enabled)
3. ✅ Auto-DM sent with file link
4. ✅ Logs show: "DM sent successfully"

---

**Next Step**: Fix Instagram API permissions by regenerating token with `instagram_manage_comments` permission.
