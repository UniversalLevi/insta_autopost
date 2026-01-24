# Browser Automation Setup Guide

Browser automation enables real likes, follows, and story views that aren't available via Instagram Graph API.

## Installation

1. **Install Playwright**
   ```bash
   pip install playwright
   ```

2. **Install Browser Binaries**
   ```bash
   playwright install chromium
   ```

## Configuration

### Add Password to Account Config

Edit `config/accounts.yaml` and add your Instagram password:

```yaml
accounts:
  - account_id: "your_account_id"
    username: "your_username"
    access_token: "your_token"
    password: "your_instagram_password"  # Add this for browser automation
    proxy:
      enabled: false
    warming:
      enabled: true
      daily_actions: 10
      action_types:
        - "like"  # Will now use browser automation!
        - "comment"
```

**Note**: The password is used only for initial login. After that, cookies are saved and reused.

## How It Works

1. **First Run**: Browser opens, logs into Instagram using your password
2. **Session Saved**: Cookies are saved to `data/sessions/`
3. **Next Runs**: Uses saved cookies, no password needed (until cookies expire)
4. **Like Action**: Navigates to post and clicks like button

## Features

- ✅ **Real Likes**: Actually likes posts via browser
- ✅ **Session Persistence**: Saves login cookies
- ✅ **Account Isolation**: Separate browser instances per account
- ✅ **Fallback**: Falls back to simulated if browser fails

## Security

- Passwords are stored in plain text in config files
- Consider using environment variables in production
- Sessions are saved locally in `data/sessions/`

## Troubleshooting

**Browser won't start:**
- Run: `playwright install chromium`
- Check if Chromium is installed

**Login fails:**
- Verify password is correct
- Check if 2FA is enabled (not supported yet)
- Try deleting `data/sessions/` folder and retry

**Like action still simulated:**
- Check logs for browser errors
- Verify password is in config
- Check if browser automation initialized successfully

## Limitations

- Headless mode only (no visible browser)
- Single session per account
- Cookies expire after ~30 days
- 2FA not supported (yet)
