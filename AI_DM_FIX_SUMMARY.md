# AI DM Auto-Reply Fix Summary

## Issues Fixed

### 1. ✅ Log File Path
- **Problem**: Diagnostic scripts were looking for `logs/app.log` but actual log file is `logs/instaforge.log`
- **Fix**: Updated all diagnostic scripts to use correct log file path

### 2. ✅ Enhanced Webhook Logging
- **Problem**: Not enough logging to debug webhook issues
- **Fix**: Added comprehensive logging to webhook endpoint and message processing

### 3. ✅ Improved Error Handling
- **Problem**: Errors were silently failing
- **Fix**: Added better exception handling and logging throughout webhook processing

## Current Status

✅ **Configuration**: All correct
- OpenAI API key: Configured
- AI DM Enabled: True
- Instagram Business ID: Set (1405915827600672)

✅ **AI Reply Generation**: Working
- Test endpoint successfully generates replies

❌ **Webhook Not Receiving Messages**: This is the main issue

## How to Fix

### Step 1: Verify Webhook Subscription

1. Go to [Meta App Dashboard](https://developers.facebook.com/apps/)
2. Select your app
3. Navigate to **Webhooks** → **Instagram**
4. Check that:
   - ✅ **Callback URL**: `https://veilforce.com/webhooks/instagram`
   - ✅ **Verify Token**: Matches your `WEBHOOK_VERIFY_TOKEN` in `.env`
   - ✅ **messages** field shows **"Subscribed"** (this is critical!)

### Step 2: Test Webhook

1. In Meta App Dashboard → Webhooks → Instagram
2. Click **"Test"** button next to the `messages` field
3. This will send a test message to your webhook
4. Check your logs to see if it's received

### Step 3: Check Logs

Run this command to check if webhooks are being received:

```powershell
.\test_webhook_receiving.ps1
```

Or manually check:

```powershell
Get-Content logs/instaforge.log -Tail 100 | Select-String "webhook|AI_DM"
```

### Step 4: Verify Account Matching

The webhook uses `instagram_business_id` to match accounts. Verify:
- Your account has `instagram_business_id: '1405915827600672'` in `accounts.yaml` ✅ (already set)
- The webhook payload contains this ID in the `entry.id` field

## Common Issues

### Issue 1: Webhook Not Subscribed to "messages" Field
**Symptom**: No "Instagram webhook messages event" in logs
**Solution**: Subscribe to "messages" field in Meta App Dashboard

### Issue 2: Wrong Webhook URL
**Symptom**: Webhook verification fails
**Solution**: Ensure URL is `https://veilforce.com/webhooks/instagram` (not `/api/webhooks/instagram`)

### Issue 3: Account Not Matching
**Symptom**: "account_not_found" in logs
**Solution**: Verify `instagram_business_id` matches the ID in webhook payload

### Issue 4: 24-Hour Messaging Window
**Symptom**: Error code 10 when sending DM
**Solution**: User must have messaged you first within last 24 hours

## Testing Commands

```powershell
# Check configuration
.\diagnose_ai_dm.ps1

# Check if webhooks are being received
.\test_webhook_receiving.ps1

# Check recent logs
.\check_ai_dm_logs.ps1

# Test AI reply generation
.\test_ai_dm_simple.ps1
```

## Next Steps

1. **Verify webhook subscription** in Meta App Dashboard (most important!)
2. **Test webhook** using Meta's test button
3. **Check logs** after sending a test DM
4. **Look for** "AI_DM_WEBHOOK" entries in logs

## Expected Log Flow

When a message is received, you should see:

```
Instagram webhook POST received
Instagram webhook payload received
Instagram webhook messages event
AI_DM_WEBHOOK - action="processing_start"
AI_DM_WEBHOOK - action="config_check" - ai_dm_enabled=true
AI_DM_WEBHOOK - action="extracted_data"
AI_DM_WEBHOOK - action="processing"
AI_DM_WEBHOOK - action="reply_sent"
```

If you don't see "Instagram webhook messages event", the webhook is not receiving message notifications.
