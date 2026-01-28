# AI DM Customization Guide

## Overview

The AI Brain feature extends the AI DM Auto Reply system with per-client customization and learning capabilities. Each account can have its own customized AI personality, business information, and conversation memory.

## Features

- **Custom Branding**: Set your brand name, business type, and location
- **Personality Control**: Choose communication tone (friendly, professional, casual, etc.)
- **Business Context**: Add pricing, about information, and custom rules
- **Conversation Memory**: AI remembers previous conversations with users
- **Auto-Tagging**: Automatically tags users based on their interests
- **Custom Prompts**: Advanced users can override the system prompt completely

## Setup

### 1. Access AI Settings

Navigate to: **http://localhost:8000/ai-settings**

Or use the API endpoints directly.

### 2. Configure Your Profile

Fill in the following fields:

#### Business Information
- **Brand Name**: Your brand or business name (replaces "InstaForge" in AI context)
- **Business Type**: e.g., "E-commerce", "SaaS", "Consulting"
- **Location**: Where your business is located
- **Pricing**: How to respond to pricing questions
- **About Business**: Brief description of what you do

#### Personality & Tone
- **Communication Tone**: 
  - Friendly (Default)
  - Professional
  - Casual
  - Enthusiastic
  - Helpful
- **Language**: Primary language for responses

#### Custom Rules
Add specific rules for how the AI should behave, one per line:
```
- Always mention our 24/7 support
- Never discuss competitors
- Always ask for email before sending resources
```

#### Advanced
- **Custom System Prompt**: Completely override the default prompt (advanced users only)
- **Enable Memory**: Toggle conversation memory on/off

### 3. Save Settings

Click "Save Settings" to apply your configuration. The AI will immediately start using your custom profile.

## How It Works

### Profile-Based Customization

When a message arrives:

1. System loads your account's profile
2. Builds a customized prompt combining:
   - Base prompt (default behavior)
   - Your business information
   - Your custom rules
   - Your tone preferences
3. Sends to OpenAI with the customized prompt
4. Returns personalized reply

### Memory System

If memory is enabled:

1. **Stores Conversations**: Every user message and AI reply is stored
2. **Auto-Tagging**: Users are automatically tagged based on message content:
   - `pricing` - Asked about pricing
   - `location` - Asked about location
   - `product` - Asked about products/services
   - `support` - Asked for help
3. **Context Building**: Recent conversations are included in the prompt
4. **Learning**: AI learns user preferences and interests over time

### Memory Limits

- **Per User**: Maximum 50 messages stored
- **Retention**: Messages older than 30 days are automatically cleaned up
- **Storage**: Stored in `data/ai_memory.json`

## API Endpoints

### Get Profile
```http
GET /api/ai/profile?account_id=your_account_id
```

### Update Profile
```http
POST /api/ai/profile/update
Content-Type: application/x-www-form-urlencoded

account_id=your_account_id
brand_name=My Brand
business_type=E-commerce
tone=professional
pricing=$99/month
location=USA
about_business=We sell amazing products
custom_rules=Always mention free shipping
enable_memory=true
```

### Get Memory Statistics
```http
GET /api/ai/memory/stats?account_id=your_account_id
```

### Reset Memory
```http
POST /api/ai/memory/reset
Content-Type: application/x-www-form-urlencoded

account_id=your_account_id
user_id=optional_user_id  # Omit to reset all account memory
```

## Examples

### Example 1: E-commerce Store

**Profile:**
- Brand Name: "FashionHub"
- Business Type: "E-commerce"
- Location: "USA, Online Store"
- Pricing: "Free shipping on orders over $50. Prices start at $29.99"
- Tone: "Friendly"
- Custom Rules:
  - "Always mention free shipping on orders over $50"
  - "Never discuss competitor prices"
  - "Ask about size preferences for clothing items"

**Result**: AI will respond as "FashionHub" with friendly tone, mention free shipping, and remember user preferences.

### Example 2: SaaS Company

**Profile:**
- Brand Name: "CloudSync"
- Business Type: "SaaS"
- Location: "San Francisco, CA"
- Pricing: "Starting at $49/month with 14-day free trial"
- Tone: "Professional"
- Custom Rules:
  - "Always mention the free trial"
  - "Ask about team size for enterprise pricing"
  - "Provide link to demo video when asked"

**Result**: AI will respond professionally, emphasize the trial, and remember if users asked about enterprise features.

### Example 3: Consulting Service

**Profile:**
- Brand Name: "StrategyPro"
- Business Type: "Business Consulting"
- Location: "New York, NY"
- Pricing: "Custom quotes based on project scope"
- Tone: "Helpful"
- About Business: "We help businesses optimize their operations and grow revenue"
- Custom Rules:
  - "Always ask about their business type first"
  - "Schedule a discovery call for pricing"
  - "Provide case studies when relevant"

**Result**: AI will be helpful, ask qualifying questions, and remember what type of business each user has.

## Memory Features

### Auto-Tagging

Users are automatically tagged based on their messages:

- **pricing**: User asked about pricing
- **location**: User asked about location
- **product**: User asked about products/services
- **support**: User asked for help

Tags help the AI understand user interests and provide better context.

### Conversation Context

The AI includes recent conversation history in the prompt:

```
Recent conversation:
user: What's your pricing?
assistant: Our pricing starts at $99/month
user: Do you have a free trial?
```

This allows the AI to maintain context and provide coherent responses.

### Memory Management

- **View Stats**: Check memory statistics on the AI Settings page
- **Reset Memory**: Clear all memory for an account or specific user
- **Auto-Cleanup**: Old messages are automatically removed after 30 days

## Best Practices

### 1. Be Specific
- Provide clear, specific information about your business
- Use concrete examples in custom rules
- Include actual pricing if possible

### 2. Test Your Settings
- Use the test endpoint to verify your profile works
- Send test messages to see how the AI responds
- Adjust tone and rules based on results

### 3. Monitor Memory
- Check memory statistics regularly
- Review auto-tags to understand user interests
- Reset memory if needed for testing

### 4. Custom Rules
- Keep rules short and actionable
- One rule per line
- Use positive language ("Always do X" vs "Never do Y")

### 5. Memory Usage
- Enable memory for better personalization
- Disable if you want consistent, non-contextual replies
- Memory helps with follow-up questions

## Troubleshooting

### AI not using custom profile

1. Check that profile is saved: `GET /api/ai/profile`
2. Verify account_id matches your account
3. Check logs for errors

### Memory not working

1. Verify `enable_memory` is set to `true`
2. Check `data/ai_memory.json` exists and is writable
3. Review memory stats: `GET /api/ai/memory/stats`

### Custom prompt not working

1. Ensure custom prompt is saved correctly
2. Check for syntax errors in the prompt
3. Test with a simple prompt first

### Performance issues

1. Memory cleanup runs automatically
2. Limit custom rules to essential ones
3. Reduce memory retention if needed

## Data Storage

### Profile Data
- **File**: `data/ai_profiles.json`
- **Format**: JSON with account_id as key
- **Backup**: Recommended before major changes

### Memory Data
- **File**: `data/ai_memory.json`
- **Format**: Nested JSON (account -> user -> history)
- **Size**: Grows with usage, auto-cleanup after 30 days

## Security

- **Input Sanitization**: All user inputs are sanitized
- **No Sensitive Data**: Don't store passwords or API keys in profiles
- **Access Control**: Add authentication to API endpoints in production
- **Data Encryption**: Consider encrypting sensitive business information

## Limits

- **Max Messages per User**: 50 messages
- **Memory Retention**: 30 days
- **Custom Rules**: No hard limit (keep reasonable)
- **Custom Prompt**: No limit (but keep it focused)

## Future Enhancements

- Multi-language support per account
- Custom tag management
- Conversation export
- Analytics dashboard
- A/B testing for prompts
- Integration with CRM systems

## Support

For issues or questions:
1. Check logs for errors
2. Review this documentation
3. Test with `/api/test/ai-reply` endpoint
4. Verify profile and memory data files
