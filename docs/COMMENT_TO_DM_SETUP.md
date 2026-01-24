# Comment-to-DM Automation Setup Guide

## Overview

Extended Instagram automation system with "comment-to-auto-DM" funnel that behaves like LinkDM/autodms.in services. Automatically sends DMs to users when they comment on your posts.

## Features

✅ **Track Last Processed Comment ID** - Prevents duplicate processing  
✅ **Flexible Trigger Logic** - AUTO mode (any comment) or keyword-based  
✅ **One DM Per User Per Post Per Day** - Prevents spam  
✅ **Configurable Safety Limits** - Daily DM limits and cooldown intervals  
✅ **Comprehensive Logging** - Logs every step (comment received, trigger decision, DM sent/skipped/failed)  
✅ **Retry Logic** - Exponential backoff for API failures  
✅ **Graceful Error Handling** - Handles API failures with retry and logging  

## Configuration

### 1. Enable in `config/accounts.yaml`

```yaml
comment_to_dm:
  enabled: true  # Enable/disable automation
  trigger_keyword: "AUTO"  # "AUTO" = any comment, or specific keyword
  dm_message_template: "Hey {username} 👋 Thanks for commenting! Here's the link you requested: {link}"
  link_to_send: "https://example.com/file.pdf"  # PDF, checkout, or resource link
  daily_dm_limit: 50  # Maximum DMs per day per account
  cooldown_seconds: 5  # Minimum seconds between DMs
```

### 2. Configuration Options

#### `enabled` (boolean)
- `true`: Automation is active
- `false`: Automation is disabled

#### `trigger_keyword` (string)
- `"AUTO"` or empty: **Every comment** (any text) triggers a DM
- Specific keyword (e.g., `"pdf"`, `"link"`, `"guide"`): Only comments containing that word trigger a DM (case-insensitive)

#### `dm_message_template` (string, optional)
Message template with placeholders:
- `{username}` - Commenter's username
- `{@username}` - Commenter's username with @ symbol
- `{link}` - Link from `link_to_send` or post-specific file
- `{post}` - Post caption (truncated to 50 chars)

Example:
```
"Hey {username} 👋 Thanks for commenting! Here's the link you requested: {link}"
```

#### `link_to_send` (string, optional)
Link to include in DM:
- URL: `https://example.com/file.pdf`
- Local file: `file:///C:/Users/name/Downloads/file.pdf`
- Or leave empty and use post-specific files

#### `daily_dm_limit` (integer, default: 50)
Maximum number of DMs to send per day per account (safety limit).

#### `cooldown_seconds` (integer, default: 5)
Minimum seconds to wait between sending DMs (prevents rate limiting).

## How It Works

### 1. Comment Detection
- System monitors your recent posts every 60 seconds
- Uses Meta Instagram Graph API to detect new comments
- **Tracks last processed comment ID per post** to avoid duplicates

### 2. Trigger Evaluation
- If `trigger_keyword` is "AUTO" or empty: **Any comment** triggers DM
- If specific keyword: Only comments containing that word trigger (case-insensitive)

### 3. Duplicate Prevention
- **One DM per user per post per day** - Prevents spam
- Tracks which users received DMs today for each post

### 4. Safety Checks
- **Daily limit**: Won't exceed `daily_dm_limit` per account per day
- **Cooldown**: Waits `cooldown_seconds` between DMs
- **Retry logic**: Retries failed DMs with exponential backoff (max 3 attempts)

### 5. DM Delivery
- Generates personalized message from template
- Includes configured link (PDF, checkout, etc.)
- Sends DM via Instagram Graph API

## Logging

Every step is logged with detailed information:

```
"Comment received" - When a new comment is detected
"Trigger decision: comment matches" - When trigger keyword matches
"DM sent successfully" - When DM is successfully sent
"DM skipped: already sent to user today" - When duplicate prevented
"DM skipped: safety limit" - When daily limit/cooldown reached
"DM failed" - When DM sending fails (with error details)
```

## Testing

### 1. Enable Automation
```yaml
comment_to_dm:
  enabled: true
  trigger_keyword: "AUTO"
```

### 2. Restart Server
```bash
python web_server.py
```

### 3. Comment on Your Post
- Comment on one of your recent posts
- Wait up to 60 seconds for next check cycle

### 4. Check Logs
```bash
tail -f logs/instaforge.log | grep -i "dm"
```

Look for:
- `"Comment received"`
- `"Trigger decision: comment matches"`
- `"DM sent successfully"`

### 5. Check Status via API
```bash
curl http://localhost:8000/api/comment-to-dm/status?account_id=YOUR_ACCOUNT_ID
```

## Troubleshooting

### Comments Not Detected
- Check Instagram API permissions: `instagram_manage_comments` required
- Verify access token is valid
- Check logs for API errors

### DMs Not Sending
- Check Instagram API permissions: `instagram_manage_messages` required
- Verify daily limit not reached
- Check cooldown period
- Review error logs for API failures

### Duplicate DMs
- System tracks last processed comment ID per post
- System tracks users per post per day
- If duplicates occur, check logs for processing errors

## API Endpoints

### Get Status
```http
GET /api/comment-to-dm/status?account_id=ACCOUNT_ID
```

Response:
```json
{
  "automation_enabled": true,
  "daily_dm_count": 5,
  "daily_limit": 50,
  "users_dm_today_count": 5,
  "cooldown_seconds": 5
}
```

### Update Config
```http
PUT /api/comment-to-dm/config
{
  "account_id": "ACCOUNT_ID",
  "enabled": true,
  "trigger_keyword": "pdf",
  "daily_dm_limit": 100
}
```

## Safety Features

1. **Daily Limits**: Prevents exceeding API rate limits
2. **Cooldown Intervals**: Spreads out DM sends
3. **One DM Per User Per Post Per Day**: Prevents spam
4. **Retry Logic**: Handles temporary API failures
5. **Comprehensive Logging**: Full traceability

## Best Practices

1. **Start with lower limits**: Set `daily_dm_limit: 10` initially
2. **Monitor logs**: Watch for errors and adjust accordingly
3. **Test with keyword mode**: Use specific keyword before enabling AUTO mode
4. **Check Instagram API limits**: Respect Instagram's rate limits
5. **Use post-specific files**: Attach different files to different posts

---

**Need Help?** Check `docs/COMMENT_PERMISSIONS.md` for Instagram API permission setup.
