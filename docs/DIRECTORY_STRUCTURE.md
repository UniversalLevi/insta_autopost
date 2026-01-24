# InstaForge Directory Structure

## Overview
This document describes the organization and purpose of each directory and key file in the InstaForge project.

```
InstaForge/
├── config/                 # Configuration files
├── data/                   # Application data storage
├── docs/                   # Documentation
├── logs/                   # Application logs
├── scripts/                # Utility scripts
├── src/                    # Source code
├── uploads/                # Temporary uploads
├── web/                    # Web dashboard
├── web_server.py          # Main web server entry point
├── main.py                # Alternative entry point
├── requirements.txt       # Python dependencies
└── README.md              # Project overview
```

---

## 📁 Directory Details

### `/config`
**Purpose**: Application and account configuration files

**Files**:
- `accounts.yaml` - Instagram account credentials and settings
- `settings.yaml` - Global application settings (rate limits, logging, etc.)
- `app_credentials.yaml` - Application credentials (Cloudinary, etc.)

**Key Configuration**:
- Account tokens and credentials
- Warming settings
- Comment-to-DM configuration
- Proxy settings
- Rate limiting settings

---

### `/data`
**Purpose**: Persistent data storage

**Contents**:
- `post_dm_config.json` - Per-post DM file attachments
- Other application state files

---

### `/docs`
**Purpose**: Project documentation

**Key Documents**:
- `FEATURES.md` - Complete features list (this file)
- `SETUP.md` - Setup and installation guide
- `COMMENT_TO_DM_SETUP.md` - Comment-to-DM automation guide
- `TOKEN_GUIDE.md` - Instagram token generation
- `TOKEN_GENERATION_GUIDE.md` - Detailed token generation steps
- `FACEBOOK_VS_INSTAGRAM_TOKEN.md` - Token type differences
- `COMMENT_PERMISSIONS.md` - Required permissions guide
- `CLOUDINARY.md` - Cloudinary setup guide
- `TROUBLESHOOTING.md` - Common issues and solutions
- `ARCHITECTURE.md` - System architecture
- `DIRECTORY_STRUCTURE.md` - This file

---

### `/logs`
**Purpose**: Application log files

**Files**:
- `instaforge.log` - Main application log (JSON format)
- Log rotation files (backups)

**Log Format**: Structured JSON logging with timestamps

---

### `/scripts`
**Purpose**: Utility and diagnostic scripts

**Scripts**:
- `check_token_detailed.py` - Verify Instagram token validity
- `verify_token_permissions.py` - Check token permissions
- `check_recent_comments.py` - Check recent comments
- `test_instagram_token.py` - Test Instagram token
- `test_facebook_token.py` - Test Facebook token
- `test_fb_token_with_ig.py` - Test Facebook token with Instagram
- `generate_token.py` - Generate access tokens
- `setup_cloudinary.ps1` - Cloudinary setup script
- `create_env_file.ps1` - Create .env file
- `stop_server.ps1` - Stop server processes

---

### `/src`
**Purpose**: Main application source code

#### `/src/api`
Instagram Graph API client and rate limiting
- `instagram_client.py` - Instagram API client
- `rate_limiter.py` - Rate limiting implementation

#### `/src/app.py`
Main application entry point and initialization

#### `/src/auth`
Authentication helpers
- `oauth_helper.py` - OAuth utilities

#### `/src/automation/browser`
Browser automation (Playwright)
- `browser_wrapper.py` - Browser wrapper
- `browser_manager.py` - Browser session management
- `browser_service.py` - Browser service
- `session_manager.py` - Session management
- `actions/like_action.py` - Like action implementation

#### `/src/core`
Core system components
- `scheduler.py` - Task scheduling
- `policy_engine.py` - Policy-based decisions
- `state_manager.py` - State management
- `health_monitor.py` - Health monitoring

#### `/src/features/comments`
Comment automation features
- `comment_service.py` - Comment retrieval and replies
- `comment_monitor.py` - Comment monitoring
- `comment_to_dm_service.py` - Comment-to-DM automation
- `post_dm_config.py` - Per-post DM configuration

#### `/src/models`
Data models
- `account.py` - Account model
- `post.py` - Post model

#### `/src/proxies`
Proxy management
- `proxy_manager.py` - Proxy manager

#### `/src/safety`
Safety and rate limiting
- `throttler.py` - Action throttling
- `cooldown_manager.py` - Cooldown management
- `daily_limits.py` - Daily activity limits
- `pattern_detector.py` - Pattern detection
- `risk_assessor.py` - Risk assessment

#### `/src/services`
Business logic services
- `account_service.py` - Account management
- `posting_service.py` - Posting service

#### `/src/utils`
Utility functions
- `config_loader.py` - Configuration loading
- `exceptions.py` - Custom exceptions
- `logger.py` - Logging utilities

#### `/src/warming`
Account warming system
- `warming_service.py` - Warming service
- `warming_actions.py` - Warming actions

---

### `/uploads`
**Purpose**: Temporary file uploads

**Contents**: User-uploaded files before processing

---

### `/web`
**Purpose**: Web dashboard and API

#### `/web/static`
Static assets
- `/css/style.css` - Stylesheet
- `/js/` - JavaScript files:
  - `app.js` - Main app logic
  - `posting.js` - Post creation
  - `posts.js` - Posts management
  - `logs.js` - Log viewer
  - `settings.js` - Settings management

#### `/web/templates`
HTML templates
- `index.html` - Post creation page
- `posts.html` - Published posts view
- `logs.html` - Log viewer
- `settings.html` - Settings page
- `base.html` - Base template

#### `/web`
API and helpers
- `api.py` - API route handlers
- `auth.py` - Authentication
- `main.py` - FastAPI app setup
- `models.py` - API models
- `cloudinary_helper.py` - Cloudinary integration
- `cloudflare_helper.py` - Cloudflare utilities
- `ngrok_helper.py` - Ngrok utilities

---

## 🔑 Key Files

### `web_server.py`
Main web server entry point. Starts FastAPI server on port 8000.

### `main.py`
Alternative entry point for programmatic usage.

### `requirements.txt`
Python package dependencies.

### `README.md`
Project overview and quick start guide.

---

## 📝 File Naming Conventions

- **Python files**: `snake_case.py`
- **Config files**: `snake_case.yaml` or `snake_case.json`
- **Documentation**: `UPPER_CASE.md` or `Title_Case.md`
- **Scripts**: `snake_case.py` or `snake_case.ps1`

---

## 🗂️ Data Flow

1. **Configuration** → Loaded from `/config` at startup
2. **Uploads** → Stored in `/uploads` temporarily
3. **Media** → Uploaded to Cloudinary, URLs stored
4. **Posts** → Created via API, published to Instagram
5. **Comments** → Monitored, processed, DMs sent
6. **Logs** → Written to `/logs/instaforge.log`
7. **State** → Stored in `/data` directory

---

## 🔒 Security Notes

- **Credentials**: Stored in `config/accounts.yaml` (keep secure!)
- **Tokens**: Instagram access tokens in config files
- **Sessions**: Managed via FastAPI sessions
- **Logs**: May contain sensitive data (review before sharing)

---

*Last Updated: 2026-01-24*
