# Setup Guide

## Initial Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Instagram Account**
   - Edit `config/accounts.yaml` with your account details
   - Get access token (see Token Setup below)

3. **Configure Cloudinary** (Recommended)
   - See `docs/CLOUDINARY.md` for detailed instructions
   - Or run: `scripts/setup_cloudinary.ps1`

4. **Start Server**
   ```bash
   python web_server.py
   ```

## Token Setup

### Getting Instagram Access Token

1. **Option 1: Using Graph API Explorer**
   - Go to: https://developers.facebook.com/tools/explorer/
   - Select your app
   - Get User Token with permissions: `instagram_basic`, `pages_show_list`, `instagram_content_publish`
   - Exchange for Long-Lived Token (60 days)

2. **Option 2: OAuth Flow**
   - Run: `python scripts/generate_token.py`
   - Follow the prompts
   - Token will be saved automatically

3. **Update Config**
   - Add token to `config/accounts.yaml`:
   ```yaml
   accounts:
     - account_id: "YOUR_ACCOUNT_ID"
       username: "your_username"
       access_token: "YOUR_TOKEN_HERE"
   ```

## Account Requirements

- Instagram account must be **Business** or **Creator** (not Personal)
- Must be connected to a Facebook Page
- Facebook Page must be connected to your Facebook App

## Configuration Files

- `config/accounts.yaml` - Account credentials
- `config/settings.yaml` - Application settings
- `config/app_credentials.yaml` - Facebook App credentials
- `.env` - Environment variables (Cloudinary, etc.)

For detailed token generation instructions, see `docs/TOKEN_GUIDE.md`.
