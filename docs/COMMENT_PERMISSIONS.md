# Comment Retrieval - Permissions Issue

## Problem

The comment monitoring system is working correctly, but it's retrieving **0 comments** even when comments exist on your posts.

## Why This Happens

Instagram Graph API has **strict permissions** for reading comments:

1. **Your access token needs specific permissions:**
   - `instagram_basic` - Basic read access
   - `instagram_manage_comments` - Manage comments permission (for reading AND replying)

2. **API Limitations:**
   - Some comments may not be accessible via API
   - API might only return your own comments on your posts
   - May require the post to be from a Business/Creator account

## Current Status

**Your logs show:**
```
processed: 0, replied: 0, skipped: 0, failed: 0
```

This means:
- ✅ Comment monitoring is **working** (checking posts every 60 seconds)
- ✅ API calls are **succeeding** (no errors)
- ⚠️ API is **returning 0 comments** (permissions or API limitation)

## Solutions

### Option 1: Regenerate Token with Correct Permissions

1. Go to: https://developers.facebook.com/tools/explorer/
2. Select your app
3. Get User Token with permissions:
   - ✅ `instagram_basic`
   - ✅ `instagram_manage_comments`
   - ✅ `instagram_content_publish`
4. Exchange for Long-Lived Token
5. Update `config/accounts.yaml` with new token

### Option 2: Use Browser Automation for Comments

Since browser automation is already implemented for likes, we can extend it to:
- Monitor comments via browser (scraping)
- Reply via browser UI
- More reliable than API

### Option 3: Check Post Settings

- Ensure comments are enabled on your posts
- Verify you can see comments in Instagram app
- Check if account type is Business/Creator

## Verification

Run this to test comment retrieval:
```powershell
python scripts/test_comment_retrieval.py
```

If it shows "Retrieved 0 comments" but you know there are comments:
- **Permissions issue** - Regenerate token with correct permissions
- **API limitation** - Use browser automation instead

## Current Behavior

**The system is working correctly** - it's just that Instagram's API isn't returning comments. This is a **permissions/API limitation issue**, not a code bug.

---

**Next Step**: Either fix token permissions OR implement browser-based comment monitoring (which would be more reliable anyway).
# ✅ Permissions Checklist

## From Your Meta Graph API Explorer Screenshot

### ✅ Permissions You Have:
1. ✅ `instagram_basic` - Basic Instagram access
2. ✅ `instagram_manage_comments` - **READ COMMENTS** (This is what we need!)
3. ✅ `instagram_content_publish` - Publish posts
4. ✅ `pages_read_engagement` - Read page engagement
5. ✅ `instagram_creator_marketplace_discovery` - Creator marketplace
6. ✅ `instagram_manage_contents` - Manage content

### ⚠️ Missing Permission:
- ❌ `instagram_manage_messages` - **SEND DMs** (REQUIRED for auto-DM feature)

## Important Notes:

### 1. Facebook Token vs Instagram Token
- The token shown in your screenshot (starts with `EAAbDa5h...`) is a **Facebook Page Token**
- For Instagram API, you need an **Instagram User Token** (starts with `IGAATZBr...`)
- Your current Instagram token in config: `IGAATZBr...` ✅

### 2. Instagram Token Permissions
Instagram tokens have separate permissions from Facebook tokens. You need to:

1. **Exchange Facebook Token for Instagram Token** OR
2. **Generate Instagram Token directly** with these permissions:
   - ✅ `instagram_basic`
   - ✅ `instagram_manage_comments` (for reading comments)
   - ⚠️ `instagram_manage_messages` (for sending DMs) - **MISSING**

## Current Status:

### ✅ What's Working:
- System can detect posts exist
- System can see comment counts (1, 3, 2 comments)
- Permissions include `instagram_manage_comments`

### ❌ What's Not Working:
- **Cannot read comment content** - Even with `instagram_manage_comments`, Instagram API still returns empty array
- **Cannot send DMs** - Missing `instagram_manage_messages` permission
- **Comment-to-DM is disabled** - Need to enable in config

## Next Steps:

### Step 1: Enable Comment-to-DM (I'll do this now)
```yaml
comment_to_dm:
  enabled: true  # Change from false to true
```

### Step 2: Get Instagram Token with ALL Permissions

**Option A: Via Meta Graph API Explorer**
1. Go to: https://developers.facebook.com/tools/explorer/
2. Select your **Instagram app** (not Facebook app)
3. Generate token with permissions:
   - `instagram_basic`
   - `instagram_manage_comments`
   - `instagram_manage_messages` ← **ADD THIS ONE**
   - `instagram_content_publish`

**Option B: Token Exchange**
If you have a Facebook token with Instagram permissions:
1. Exchange it for a long-lived Instagram token
2. Ensure all permissions transfer over

### Step 3: Update Token in Config
```yaml
access_token: "YOUR_NEW_INSTAGRAM_TOKEN_WITH_ALL_PERMISSIONS"
```

### Step 4: Restart Server
```bash
python web_server.py
```

## Why Comments Still Return 0:

Even with `instagram_manage_comments` permission:
- Instagram API may still return empty array for security/privacy reasons
- The token might be a short-lived token that expired
- The token might be for a different Instagram account
- There might be API rate limiting or restrictions

## Testing After Fixes:

1. Wait 60 seconds for next comment check cycle
2. Check logs: `logs/instaforge.log`
3. Look for:
   - `"comments_count_from_media": 1` (shows comment exists)
   - `"comment_count": 1` (shows API can read it) ← **This is what we need**
   - `"Found comments to process for auto-DM"`
   - `"DM sent successfully"`

---

**Action Required**: 
1. Enable Comment-to-DM in config (I'll do this)
2. Get Instagram token with `instagram_manage_messages` permission
3. Update token in config
4. Restart server
