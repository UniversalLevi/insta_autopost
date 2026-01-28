# AI DM Auto-Reply Testing Guide

## Quick Test Commands

### 1. Check Configuration Status
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-dm-status" -Method GET | ConvertTo-Json
```

**Expected Result:**
- `openai_configured: true` - OpenAI API key is set
- `ai_dm_enabled: true` - AI DM is enabled for your account
- `instagram_business_id` should be set (for webhook matching)

### 2. Test AI Reply Generation
```powershell
$body = @{
    message = "Hello! How much does your service cost?"
    account_id = "1405915827600672"
}
Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded" | ConvertTo-Json
```

**Expected Result:**
- `status: "success"`
- `reply` contains an AI-generated response
- Reply should be friendly, professional, and relevant

### 3. Run Complete Test Suite
```powershell
.\test_ai_dm_complete.ps1
```

This will test:
- ✅ Configuration status
- ✅ AI reply generation with multiple test messages
- ✅ Rate limiting (max 10 replies per user per day)
- ✅ Tracking file creation
- ✅ Webhook configuration

## Real-World Testing (Instagram DM)

### Step 1: Verify Webhook is Set Up
1. Go to [Meta App Dashboard](https://developers.facebook.com/apps/)
2. Navigate to **Webhooks** → **Instagram**
3. Verify:
   - ✅ `messages` field is subscribed
   - ✅ Webhook URL is correct: `https://veilforce.com/webhooks/instagram`
   - ✅ Verify token matches your `WEBHOOK_VERIFY_TOKEN`

### Step 2: Send a Test DM
1. Open Instagram (mobile app or web)
2. Send a DM to your account: **@mr_tony.87**
3. Send a message like: "Hello! What services do you offer?"

### Step 3: Check for Reply
- **Expected:** You should receive an AI-generated reply within 3-6 seconds
- **If no reply:** Check the logs (see below)

### Step 4: Check Logs
```powershell
# View recent AI DM logs
Get-Content logs/app.log -Tail 100 | Select-String "AI_DM"

# Or view all logs
Get-Content logs/app.log | Select-String "AI_DM_WEBHOOK"
```

**Look for these log entries:**
- `AI_DM_WEBHOOK - action="processing_start"` - Webhook received
- `AI_DM_WEBHOOK - action="extracted_data"` - Message data extracted
- `AI_DM_WEBHOOK - action="processing"` - AI reply being generated
- `AI_DM_WEBHOOK - action="reply_sent"` - ✅ Reply sent successfully
- `AI_DM_WEBHOOK - action="reply_failed"` - ❌ Failed to send (check error)

## Troubleshooting

### Issue: No Reply Received

**Check 1: Is AI DM Enabled?**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/test/ai-dm-status" -Method GET
```
- Verify `ai_dm_enabled: true` for your account

**Check 2: Is OpenAI Configured?**
- Verify `openai_configured: true`
- Check `.env` file has `OPENAI_API_KEY` set

**Check 3: Webhook Received?**
```powershell
Get-Content logs/app.log -Tail 50 | Select-String "Instagram webhook"
```
- Should see: "Instagram webhook messages event"

**Check 4: Account Matching?**
- Verify `instagram_business_id` is set in `accounts.yaml`
- Check logs for: `"account_not_found"` or `"Webhook account matched"`

**Check 5: Rate Limit?**
- Check `data/ai_dm_tracking.json`
- Each user can only receive 10 replies per day
- Counts reset at midnight UTC

**Check 6: 24-Hour Messaging Window?**
- Instagram only allows DMs to users who messaged you first
- The user must have sent you a message within the last 24 hours
- Look for error code `10` in logs: "24_hour_window"

### Issue: Reply is Generic/Fallback

**Check OpenAI API:**
- Verify API key is valid
- Check OpenAI billing is set up
- Look for errors: `"openai_not_configured"` or `"quota_exceeded"`

### Issue: Webhook Not Receiving Messages

**Check Webhook Subscription:**
1. Meta App Dashboard → Webhooks → Instagram
2. Verify `messages` field shows "Subscribed"
3. Test webhook: Click "Test" button in Meta dashboard

**Check Webhook URL:**
- Must be publicly accessible (not localhost)
- Must use HTTPS (not HTTP)
- Must return 200 OK for verification

## Production Testing

For production server (veilforce.com):

```powershell
# Change base URL
$baseUrl = "https://veilforce.com"

# Test status
Invoke-RestMethod -Uri "$baseUrl/api/test/ai-dm-status" -Method GET

# Test reply
$body = @{
    message = "Test message"
    account_id = "1405915827600672"
}
Invoke-RestMethod -Uri "$baseUrl/api/test/ai-reply" -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
```

## Expected Behavior

✅ **Working Correctly:**
- Receives DM via webhook
- Generates AI reply within 3-6 seconds
- Sends reply via Instagram API
- Logs all actions with `AI_DM_WEBHOOK` prefix
- Respects rate limit (10 replies/user/day)

❌ **Common Issues:**
- Webhook not subscribed to `messages` field
- `instagram_business_id` not set (can't match account)
- OpenAI API key missing or invalid
- 24-hour messaging window expired
- Rate limit exceeded (10 replies already sent today)
- Instagram API permissions missing (`instagram_manage_messages`)

## Log Examples

**Successful Flow:**
```
AI_DM_WEBHOOK - action="processing_start"
AI_DM_WEBHOOK - action="config_check" - ai_dm_enabled=true
AI_DM_WEBHOOK - action="extracted_data" - has_user_id=true, has_message_text=true
AI_DM_WEBHOOK - action="processing" - message_preview="Hello!..."
AI_DM_REPLY - action="generating"
AI_DM_REPLY - action="generated" - reply_preview="Hi there!..."
AI_DM_WEBHOOK - action="reply_sent" - dm_id="..."
```

**Failed Flow:**
```
AI_DM_WEBHOOK - action="skipped" - reason="ai_dm_disabled"
AI_DM_WEBHOOK - action="skipped" - reason="missing_user_id"
AI_DM_WEBHOOK - action="skipped" - reason="empty_message"
AI_DM_WEBHOOK - action="reply_failed" - error_code=10 (24-hour window)
```
