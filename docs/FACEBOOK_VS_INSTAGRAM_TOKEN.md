# Facebook Token vs Instagram Token

## Current Situation

You provided a **Facebook token** (starts with `EAA`), but you need an **Instagram token** (starts with `IGAAT`) to access Instagram directly.

## Key Differences

### Facebook Token (`EAA...`)
- ✅ Can access Facebook pages and user data
- ❌ **Cannot directly access Instagram accounts**
- ✅ Can access Instagram IF Instagram is connected to a Facebook Page
- Used for: Facebook API, Page management

### Instagram Token (`IGAAT...`)
- ✅ Can directly access Instagram Business accounts
- ✅ Can read comments, send DMs, publish posts
- ✅ Works directly with Instagram account ID
- Used for: Instagram Graph API

## Your Current Setup

- **Instagram Account ID**: `1405915827600672`
- **Username**: `mr_tony.87`
- **Facebook Token**: Valid but cannot access Instagram directly
- **Problem**: No Facebook pages connected, so can't use Facebook token

## Solution: Get Instagram Token

### Step 1: Go to Graph API Explorer
https://developers.facebook.com/tools/explorer/

### Step 2: Select Your App
- Choose your Instagram app (not Facebook app)

### Step 3: Generate Instagram Token
1. Click "Generate Access Token"
2. **Important**: Make sure you're generating an **Instagram** token, not Facebook token
3. Select these permissions:
   - `instagram_basic`
   - `instagram_manage_comments` ← **CRITICAL**
   - `instagram_manage_messages` ← **CRITICAL**
   - `instagram_content_publish`

### Step 4: Verify Token Type
- ✅ Instagram token starts with: `IGAAT...`
- ❌ Facebook token starts with: `EAA...`

### Step 5: Update Config
Replace the token in `config/accounts.yaml`:
```yaml
access_token: "IGAAT..."  # Instagram token, not EAA...
```

## Alternative: Use Facebook Page Token

If you want to use Facebook token:

1. **Create a Facebook Page**
   - Go to: https://www.facebook.com/pages/create

2. **Connect Instagram to Page**
   - Go to Page Settings
   - Connect Instagram account

3. **Get Page Access Token**
   - Use Graph API Explorer
   - Select your page (not user)
   - Generate token with Instagram permissions

4. **Use Page Token**
   - Page token can access connected Instagram account

## Quick Check

After updating token, run:
```bash
python scripts/check_token_detailed.py
```

You should see:
- ✅ Test 1: Account info retrieved
- ✅ Test 2: Posts retrieved
- ✅ Test 3: Comments retrieved

## Current Token Status

- **Facebook Token**: ✅ Valid but ❌ Cannot access Instagram
- **Instagram Token**: ❌ Invalid/Expired (needs regeneration)

**Action Required**: Generate new Instagram token with required permissions.
