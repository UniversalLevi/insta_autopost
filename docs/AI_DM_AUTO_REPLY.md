# AI DM Auto Reply Feature

## Overview

The AI DM Auto Reply feature automatically responds to incoming Instagram Direct Messages using OpenAI's GPT-4o-mini model. It generates natural, human-like replies that sound friendly and professional.

## Features

- **AI-Powered Replies**: Uses OpenAI GPT-4o-mini to generate contextual, natural responses
- **Rate Limiting**: Maximum 10 replies per user per day to prevent spam
- **Human-like Delays**: Random 3-6 second delay before replying to appear more natural
- **Error Handling**: Graceful fallback if OpenAI API fails
- **Persistent Tracking**: Tracks replies per user to enforce rate limits across restarts
- **Secure**: Input sanitization and validation

## Setup

### 1. Environment Variables

Add your OpenAI API key to `.env`:

```bash
OPENAI_API_KEY=sk-proj-your-key-here
```

Get your API key from: https://platform.openai.com/api-keys

### 2. Enable for Account

Edit `data/accounts.yaml` and add AI DM config:

```yaml
accounts:
  - account_id: your_account_id
    username: your_username
    access_token: your_token
    ai_dm:
      enabled: true
```

Or use the web dashboard to enable it.

## Configuration

### Account-Level Configuration

```yaml
ai_dm:
  enabled: true  # Enable/disable AI DM auto-reply
```

## How It Works

1. **Webhook Receives DM**: When Instagram sends a webhook for a new message
2. **Check if Enabled**: System checks if AI DM is enabled for the account
3. **Rate Limit Check**: Verifies user hasn't exceeded 10 replies today
4. **Delay**: Waits 3-6 seconds (random) to appear human
5. **Generate Reply**: Calls OpenAI API with the incoming message
6. **Send Reply**: Sends the AI-generated reply via Instagram Messaging API
7. **Logging**: All actions are logged for debugging

## System Prompt

The AI uses this exact system prompt:

```
You are a friendly, professional Instagram DM assistant for InstaForge.

Rules:
- Sound human
- Be polite
- Be short and clear
- Never say you are AI
- Never mention OpenAI
- Never say you are a bot
- Use light emojis when appropriate

Context:
Brand: InstaForge
Location: India
Service: Instagram automation and growth tools

If user greets → greet back
If user asks price → explain briefly
If user asks location → say India, online service
If confused → help politely
If rude → stay calm

Never hallucinate.
If unsure → say you will check.

Always stay in character.
```

## Rate Limiting

- **Per User**: Maximum 10 replies per user per day
- **Tracking**: Stored in `data/ai_dm_tracking.json`
- **Auto-cleanup**: Old entries (7+ days) are automatically removed

## Error Handling

If OpenAI API fails:
- Returns fallback message: "Sorry for the delay 😊 Please try again."
- Logs error for debugging
- Does not crash the system

## Testing

### Manual Test Endpoint

Test the AI reply generation:

```bash
POST /api/test/ai-reply
Content-Type: application/x-www-form-urlencoded

message=Hello! How much does your service cost?
account_id=your_account_id
```

### Unit Tests

Run tests:

```bash
pytest tests/test_ai_dm_handler.py -v
```

## Logging

All AI DM actions are logged with these fields:
- `action`: Action type (generating, generated, failed, etc.)
- `account_id`: Account identifier
- `user_id`: User identifier
- `message_id`: Message ID (if available)
- `message_preview`: First 100 chars of message
- `reply_preview`: First 100 chars of reply

## Security

- **Input Sanitization**: All user input is sanitized to prevent injection
- **No Token Logging**: API keys are never logged
- **Webhook Validation**: Webhook signatures should be validated (add this in production)

## Troubleshooting

### AI replies not working

1. Check `OPENAI_API_KEY` is set in `.env`
2. Verify account has `ai_dm.enabled: true`
3. Check logs for errors
4. Verify rate limit hasn't been exceeded

### Rate limit issues

- Check `data/ai_dm_tracking.json` for current counts
- Each user can receive max 10 replies per day
- Counts reset at midnight UTC

### OpenAI API errors

- Check API key is valid
- Verify billing is set up at https://platform.openai.com/account/billing
- Check API quota hasn't been exceeded

## Files

- `src/features/ai_dm/ai_dm_handler.py` - Main handler
- `src/features/ai_dm/ai_dm_tracking.py` - Rate limiting tracking
- `web/instagram_webhook.py` - Webhook integration
- `data/ai_dm_tracking.json` - Persistent tracking data

## Integration

The feature is integrated into the webhook handler at `web/instagram_webhook.py`. When a message webhook is received:

1. Checks if AI DM is enabled for the account
2. Extracts message data from webhook payload
3. Calls `AIDMHandler.process_incoming_dm()`
4. Sends reply via Instagram Messaging API

## Future Enhancements

- Customizable system prompts per account
- Configurable rate limits
- Support for multiple languages
- Conversation context/memory
- Custom fallback messages
