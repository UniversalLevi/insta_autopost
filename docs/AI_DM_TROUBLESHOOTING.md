# AI DM Auto Reply - Troubleshooting Guide

## Issue: No Reply Being Sent

If messages are received but no AI reply is sent, follow these steps:

### 1. Check Configuration

Visit the diagnostic endpoint:
```
GET /api/test/ai-dm-status
```

This will show:
- If OpenAI API is configured
- Which accounts have AI DM enabled
- Account IDs and usernames
- Instagram Business IDs (if set)

### 2. Check Webhook Setup

**Important**: Instagram webhooks must be subscribed to the `messages` field.

To verify:
1. Go to Meta App Dashboard
2. Navigate to Webhooks
3. Check that `messages` field is subscribed for Instagram
4. Verify the webhook URL is correct: `https://your-domain.com/webhooks/instagram`

### 3. Check Account Matching

The webhook uses `instagram_business_id` to match accounts. If your account doesn't have this set:

**Option A**: Add `instagram_business_id` to your account in `data/accounts.yaml`:
```yaml
accounts:
  - account_id: '1405915827600672'
    username: mr_tony.87
    instagram_business_id: '1405915827600672'  # Add this
    ai_dm:
      enabled: true
```

**Option B**: The system will fallback to using the account if only one account exists.

### 4. Check Logs

Look for these log entries when a message arrives:

```
AI_DM_WEBHOOK - action="processing_start"
AI_DM_WEBHOOK - action="config_check" - ai_dm_enabled should be true
AI_DM_WEBHOOK - action="extracted_data" - should have user_id and message_text
AI_DM_WEBHOOK - action="processing" - should show message preview
AI_DM_WEBHOOK - action="reply_sent" - confirms reply was sent
```

### 5. Common Issues

#### Issue: "account_not_found" in logs
**Solution**: The webhook can't match the Instagram Business ID to your account. Add `instagram_business_id` to your account config.

#### Issue: "ai_dm_disabled" in logs
**Solution**: Check that `ai_dm.enabled: true` is set in `data/accounts.yaml`.

#### Issue: "missing_user_id" in logs
**Solution**: The webhook payload structure might be different. Check the logs for the `value` field to see the actual structure.

#### Issue: "empty_message" in logs
**Solution**: The message might be an image/sticker/other non-text message. AI DM only replies to text messages.

#### Issue: No webhook received at all
**Solution**: 
1. Verify webhook is subscribed to `messages` field
2. Check webhook URL is accessible
3. Verify webhook verification token matches

### 6. Test Manually

Test the AI reply generation:
```
POST /api/test/ai-reply
Content-Type: application/x-www-form-urlencoded

message=Hello! How much does your service cost?
account_id=1405915827600672
```

This will show if:
- OpenAI API is working
- AI DM handler is functioning
- Configuration is correct

### 7. Check Rate Limits

If a user has already received 10 replies today, no more replies will be sent. Check:
- `data/ai_dm_tracking.json` for current counts
- Logs for "rate_limit_exceeded" messages

### 8. Verify Webhook is Receiving Messages

Check your server logs for:
```
Instagram webhook payload received
Instagram webhook messages event
```

If you don't see these, the webhook isn't receiving message events.

### 9. Instagram API Permissions

Ensure your Instagram access token has:
- `instagram_manage_messages` permission
- `pages_messaging` permission (if using Page token)

### 10. Debug Steps

1. **Enable verbose logging**: Check logs for all `AI_DM_WEBHOOK` entries
2. **Check webhook payload**: Look at the `value` field in logs to see actual structure
3. **Test with single account**: If only one account exists, it will be used as fallback
4. **Verify OpenAI key**: Test endpoint should show if API key is valid

## Quick Checklist

- [ ] `OPENAI_API_KEY` is set in `.env`
- [ ] `ai_dm.enabled: true` in `data/accounts.yaml`
- [ ] Webhook subscribed to `messages` field
- [ ] Webhook URL is accessible
- [ ] Account has `instagram_business_id` set (or only one account exists)
- [ ] Access token has messaging permissions
- [ ] User hasn't exceeded 10 replies today
- [ ] Message is text (not image/sticker)

## Still Not Working?

1. Check server logs for errors
2. Use `/api/test/ai-dm-status` to verify configuration
3. Use `/api/test/ai-reply` to test AI generation
4. Check `data/ai_dm_tracking.json` for rate limit issues
5. Verify webhook is actually receiving message events
