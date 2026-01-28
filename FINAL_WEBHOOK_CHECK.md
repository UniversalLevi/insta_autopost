# Final Webhook Configuration Check

## ✅ What's Correct in Your Meta Dashboard:

1. **Callback URL**: `https://veilforce.com/webhooks/instagram` ✅ CORRECT
2. **messages field**: Subscribed ✅ CORRECT

## ⚠️ What Needs Verification:

### Verify Token Mismatch (Most Likely Issue)

Your server expects: `my_test_token_for_instagram_verification`

**Action Required:**
1. In Meta App Dashboard → Webhooks → Instagram
2. Check the "Verify token" field (it's masked as `************`)
3. It MUST be exactly: `my_test_token_for_instagram_verification`

**If it's different:**
- **Option 1 (Recommended)**: Update Meta Dashboard to use `my_test_token_for_instagram_verification`
- **Option 2**: If you want to keep your current token, add it to `.env`:
  ```
  WEBHOOK_VERIFY_TOKEN=your_actual_token_from_meta
  ```
  Then restart your server.

## 🔍 How to Verify:

1. **Check Current Token in Meta:**
   - Go to Meta App Dashboard → Webhooks → Instagram
   - Click "Edit" on the Verify token field
   - See what token is currently set

2. **Test Webhook:**
   - In Meta Dashboard, click the "Test" button next to "messages" field
   - This will send a test webhook to your server
   - Check logs: `.\test_webhook_receiving.ps1`

3. **Verify URL is Accessible:**
   - The URL `https://veilforce.com/webhooks/instagram` must be publicly accessible
   - It must return 200 OK for GET requests (webhook verification)
   - It must accept POST requests (webhook events)

## 🚨 Common Issues:

### Issue 1: Verify Token Doesn't Match
**Symptom**: Webhook shows as subscribed but no events received
**Solution**: Make sure verify token in Meta matches `my_test_token_for_instagram_verification`

### Issue 2: Webhook Verification Failed
**Symptom**: Webhook shows as not subscribed or keeps failing
**Solution**: 
1. Make sure URL is `https://veilforce.com/webhooks/instagram` (not `/api/webhooks/instagram`)
2. Make sure verify token matches exactly
3. Click "Test" button to re-verify

### Issue 3: Server Not Accessible
**Symptom**: Meta can't reach your webhook URL
**Solution**: 
- Ensure `https://veilforce.com` is pointing to your server
- Check if server is running
- Check firewall/security settings

## 📋 Quick Checklist:

- [ ] Callback URL in Meta: `https://veilforce.com/webhooks/instagram`
- [ ] Verify Token in Meta: `my_test_token_for_instagram_verification` (or update `.env` to match Meta)
- [ ] "messages" field is subscribed
- [ ] Server is running and accessible at `https://veilforce.com`
- [ ] Clicked "Test" button in Meta Dashboard
- [ ] Checked logs after test: `.\test_webhook_receiving.ps1`

## 🧪 Test Commands:

```powershell
# Check webhook configuration
.\verify_webhook_config.ps1

# Check if webhooks are being received
.\test_webhook_receiving.ps1

# Check recent logs
.\check_ai_dm_logs.ps1
```
