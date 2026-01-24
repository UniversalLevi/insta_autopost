# Get Instagram Token via Graph API Explorer

## Step-by-Step Instructions

### Step 1: Generate Access Token with Permissions

1. **In Graph API Explorer**, click the **"Generate Access Token"** button (blue button, top right)

2. **A popup will appear** - Select these permissions:
   - ✅ `pages_show_list`
   - ✅ `instagram_basic`
   - ✅ `instagram_content_publish`
   - ✅ `pages_read_engagement`

3. Click **"Generate Access Token"** in the popup

4. **You'll be redirected** to Facebook login - authorize the app

5. **You'll be redirected back** - the new token will appear in the "Access Token" field

### Step 2: Get Your Pages

1. In Graph API Explorer, use this query:
   ```
   GET /me/accounts
   ```

2. Or with specific fields:
   ```
   GET /me/accounts?fields=id,name,access_token,instagram_business_account
   ```

3. Click **"Submit"**

4. **You should see** a response like:
   ```json
   {
     "data": [
       {
         "id": "123456789",
         "name": "Your Page Name",
         "access_token": "PAGE_ACCESS_TOKEN_HERE",
         "instagram_business_account": {
           "id": "17841444586838008"
         }
       }
     ]
   }
   ```

### Step 3: Get Instagram Token (Two Methods)

#### Method A: Use Page Access Token Directly

The `access_token` from the page response **IS** your Instagram access token!

1. Copy the `access_token` from the page that has `instagram_business_account`
2. Use this token directly in `config/accounts.yaml`

#### Method B: Get Instagram Account Info

1. Use the `instagram_business_account.id` from the response above
2. Query:
   ```
   GET /{instagram_account_id}?fields=id,username,account_type
   ```
   (Replace `{instagram_account_id}` with the ID from step above)

3. Use the **Page Access Token** from Step 2 for authentication

### Step 4: Update Your Config

Update `config/accounts.yaml`:

```yaml
accounts:
  - account_id: "your_instagram_account_id"  # From instagram_business_account.id
    username: "your_instagram_username"      # From Instagram query
    access_token: "PAGE_ACCESS_TOKEN_HERE"   # From pages query (this works as Instagram token!)
    proxy:
      enabled: false
    warming:
      enabled: true
      daily_actions: 10
      action_types:
        - "like"
        - "comment"
        - "follow"
        - "story_view"
```

### Step 5: Verify It Works

```bash
python test_account_setup.py
```

## Important Notes

- **Page Access Token = Instagram Access Token** - The access token from your Facebook Page works directly with Instagram API
- If `data` array is empty, you either:
  - Don't have any Facebook Pages
  - Your Instagram isn't connected to a Page
  - Your token doesn't have the right permissions (need to regenerate)
- If you see permissions with red X, you need to generate a new token with those permissions

## Troubleshooting

**Empty data array:**
- Make sure you have a Facebook Page
- Make sure your Instagram Business account is connected to that Page
- Make sure your token has `pages_read_engagement` permission

**No instagram_business_account in response:**
- Your Instagram account must be Business or Creator (not Personal)
- It must be connected to a Facebook Page
- Check: Instagram app → Settings → Business or Creator account → Page connection
# Token Update Guide

## ✅ Tokens Received

### Facebook Access Token
```
EAAbDa5hBPloBQqFPRr5yQg81Mo6v5AiiPv60LVjBu4JLMZBszOQmsZCzSW1n8UEZA2TnHzVqXKXtMhGAymxeV8IotcUOWUVAIFHcIxRLTHYYf18GZAMTqMmGeDVOx0nEbZBbta9FvwT7tVdI0uBpPOdoncDkGdVKwlhDWgUQNSZBZCMKWZC1BOhXtjM1wdTxRAFYRrvrDbos9UzT1q30BZB7IbaKf0qKKVOyTVZCUjZCcaL0QNvoNzJGfI2fjJccQIFuHZBAbsPi4JvHrQOQnwZDZD
```

### Instagram Access Token  
```
IGAATZBrEl8ZCSBBZAGFpaTlVeGpUSWRIQTNleEZAid2J0blpLOVJUVS0yUXNqSjNjUWo3OVVCdXBYOVdvbEZANU2VfVkJvSGM5NUI3UUhySS1qZA2d3aXJPOFNRb1JfZAExVX0xETWtOTzl2TVZAKWnl4YUU2MkFOeEljcG9HZAnNFa1RFbwZDZD
```

## Current Status

✅ **Instagram Token**: Already updated in `config/accounts.yaml`
- Current token matches the new one you provided

## Important: Verify Permissions

Your new Instagram access token should have these permissions:
- ✅ `instagram_basic` - Basic access
- ✅ `instagram_manage_comments` - **CRITICAL**: Required to read comments
- ✅ `instagram_manage_messages` - **CRITICAL**: Required to send DMs
- ✅ `instagram_content_publish` - Required to post

## Testing Your Token

After restarting the server, check if comments are now being detected:

1. **Restart Server**: `python web_server.py`
2. **Wait 60 seconds** for the next comment check cycle
3. **Check logs**: `logs/instaforge.log`
4. **Look for**:
   - `"comments_count_from_media"` - Should show actual count
   - `"API returned 0 comments but media shows comments exist"` - Will warn if permissions missing
   - `"Found comments to process for auto-DM"` - Will show when comments are detected

## Facebook Token

The Facebook access token is typically used for:
- Managing Meta/Instagram Business accounts
- Token exchange/refresh operations
- OAuth flows

If your app uses Facebook API directly, store it in:
- Environment variable: `FACEBOOK_ACCESS_TOKEN`
- Or in a secure config file (if needed)

## Next Steps

1. ✅ Instagram token is already updated
2. ⚠️ **Verify permissions** - Make sure your token has `instagram_manage_comments`
3. 🔄 **Restart server** to use the new token
4. 📊 **Check logs** to see if comments are now being detected

## Troubleshooting

If comments still show as 0:
1. Check token permissions at: https://developers.facebook.com/tools/debug/accesstoken/
2. Verify `instagram_manage_comments` permission is granted
3. Regenerate token if permission is missing

---

**Token Updated**: ✅ Instagram token is in `config/accounts.yaml`
