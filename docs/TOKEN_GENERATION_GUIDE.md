# Instagram Token Generation Guide

## Current Status
- ✅ Token format: Correct (starts with IGAAT)
- ❌ Token status: Invalid/Expired (Error 190)
- ❌ Cannot read comments: Missing permissions or invalid token

## Step-by-Step: Generate New Instagram Token

### Option 1: Using Graph API Explorer (Easiest)

1. **Go to Graph API Explorer**
   - URL: https://developers.facebook.com/tools/explorer/

2. **Select Your App**
   - Click the dropdown at the top (next to "Meta App")
   - Select your Instagram app
   - If you don't see it, you may need to create an app first

3. **Generate Token**
   - Click "Generate Access Token" button
   - A popup will appear asking for permissions

4. **Select Required Permissions**
   Check these boxes:
   - ✅ `instagram_basic` - Basic access
   - ✅ `instagram_manage_comments` - **CRITICAL: Read comments**
   - ✅ `instagram_manage_messages` - **CRITICAL: Send DMs**
   - ✅ `instagram_content_publish` - Publish posts

5. **Copy the Token**
   - The token will appear in the "Access Token" field
   - It should start with `IGAAT...`
   - Copy the ENTIRE token (it's long, ~186 characters)

6. **Make it Long-Lived (Important!)**
   - Short-lived tokens expire in 1 hour
   - Click "Debug" button next to the token
   - Look for "Expires At" - if it says "1 hour", you need to exchange it
   - To get long-lived token (60 days):
     ```
     https://graph.facebook.com/v18.0/oauth/access_token?
       grant_type=fb_exchange_token&
       client_id=YOUR_APP_ID&
       client_secret=YOUR_APP_SECRET&
       fb_exchange_token=YOUR_SHORT_TOKEN
     ```

7. **Update Config**
   - Open `config/accounts.yaml`
   - Replace `access_token` with your new token
   - Save the file

8. **Restart Server**
   ```bash
   python web_server.py
   ```

### Option 2: Using Facebook Login Flow (More Permanent)

If you need a token that doesn't expire, you'll need to:
1. Set up Facebook Login in your app
2. Use OAuth flow to get user token
3. Exchange for long-lived token
4. Set up token refresh mechanism

## Verify Your Token

After updating, run:
```bash
python scripts/check_token_detailed.py
```

You should see:
- ✅ Test 1: Account info retrieved
- ✅ Test 2: Recent posts retrieved
- ✅ Test 3: Comments retrieved (if post has comments)

## Common Issues

### Error 190: Invalid Token
- **Cause**: Token expired or revoked
- **Fix**: Generate new token

### Error 10: Permission Denied
- **Cause**: Missing `instagram_manage_comments` permission
- **Fix**: Regenerate token WITH this permission

### Token Expires Quickly
- **Cause**: Using short-lived token
- **Fix**: Exchange for long-lived token (60 days)

### Cannot Read Comments
- **Cause**: Missing `instagram_manage_comments` permission
- **Fix**: Regenerate token with this permission

## Token Types

- **Short-lived**: Expires in 1 hour (for testing)
- **Long-lived**: Expires in 60 days (for production)
- **Never expires**: Requires app review and refresh mechanism

## Quick Test

After updating token, check logs:
```bash
# Should see comments being retrieved:
"comment_count": 1  ← Not 0!
"Retrieved comments from API"
```

If you still see `comment_count: 0` but `comments_count_from_media: 1`, 
the token is missing `instagram_manage_comments` permission.
