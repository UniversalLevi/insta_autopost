# InstaForge - Complete Features Documentation

## Overview
InstaForge is a production-grade Instagram automation platform with comprehensive features for managing Instagram Business accounts, automating interactions, and maintaining account safety.

---

## 🚀 Core Features

### 1. **Automated Posting System**
**Location**: `src/services/posting_service.py`, `web/api.py`

**Capabilities**:
- ✅ Post single images to Instagram
- ✅ Post single videos to Instagram
- ✅ Post carousel posts (2-10 media items)
- ✅ Support for scheduled posts
- ✅ Automatic retry on failures (configurable retries)
- ✅ Media URL verification before posting
- ✅ Cloudinary integration for reliable media hosting
- ✅ Per-post DM file attachments (PDFs, links, resources)

**API Endpoints**:
- `POST /api/posts/create` - Create and publish a post
- `GET /api/posts` - Get published posts
- `POST /api/posts/{post_id}/publish` - Publish a scheduled post
- `POST /api/posts/{media_id}/dm-file` - Attach file/link to post for DM automation

**Web Interface**:
- Upload images/videos via web dashboard
- Create posts with captions
- View published posts
- Attach files/links to posts for auto-DM

---

### 2. **Comment-to-DM Automation (Checkout Funnel)**
**Location**: `src/features/comments/comment_to_dm_service.py`

**Capabilities**:
- ✅ Automatically detect new comments on posts
- ✅ Flexible trigger logic:
  - `AUTO` mode: Every comment triggers a DM
  - Keyword mode: Only comments containing specific keyword trigger DM
- ✅ Send personalized DMs to commenters
- ✅ Attach files/links (PDFs, checkout pages, resources) per post
- ✅ One DM per user per post per day (prevents spam)
- ✅ Configurable daily DM limits per account
- ✅ Cooldown intervals between DMs
- ✅ Tracks last processed comment ID per post
- ✅ Retry logic for failed DM sends
- ✅ Comprehensive logging of all actions

**Configuration** (`config/accounts.yaml`):
```yaml
comment_to_dm:
  enabled: true
  trigger_keyword: "AUTO"  # or specific keyword
  dm_message_template: "Hey {username} 👋 Thanks for commenting! Here's the link: {link}"
  link_to_send: "file:///path/to/file.pdf"  # Default link
  daily_dm_limit: 50
  cooldown_seconds: 60
```

**API Endpoints**:
- `GET /api/comment-to-dm/status` - Get automation status
- `GET /api/comment-to-dm/config` - Get configuration
- `PUT /api/comment-to-dm/config` - Update configuration
- `POST /api/posts/{media_id}/dm-file` - Set per-post DM file
- `GET /api/posts/{media_id}/dm-file` - Get per-post DM file
- `DELETE /api/posts/{media_id}/dm-file` - Remove per-post DM file

**Safety Features**:
- Daily DM limits (configurable per account)
- Cooldown between DMs
- Duplicate prevention (one DM per user per post per day)
- Retry logic with exponential backoff
- Error handling and logging

---

### 3. **Comment Automation & Monitoring**
**Location**: `src/features/comments/comment_service.py`, `src/features/comments/comment_monitor.py`

**Capabilities**:
- ✅ Monitor posts for new comments (checks every 60 seconds)
- ✅ Auto-reply to comments with smart templates
- ✅ Prevent duplicate replies
- ✅ Filter out own comments
- ✅ Configurable reply templates
- ✅ Track processed comments per post
- ✅ Support for multiple accounts

**Features**:
- Real-time comment monitoring
- Automatic comment retrieval from Instagram API
- Smart reply generation based on comment content
- Comment history tracking

---

### 4. **Account Warming System**
**Location**: `src/warming/warming_service.py`, `src/warming/warming_actions.py`

**Capabilities**:
- ✅ 7-day progressive warm-up schedule
- ✅ Configurable daily action limits
- ✅ Multiple action types:
  - Like posts
  - Comment on posts
  - Follow users
  - View stories
- ✅ Randomized timing to appear natural
- ✅ Per-account warming configuration

**Configuration** (`config/accounts.yaml`):
```yaml
warming:
  enabled: true
  daily_actions: 10
  action_types:
    - "like"
    - "comment"
    - "follow"
    - "story_view"
```

**Features**:
- Scheduled warming actions
- Progressive intensity (starts slow, increases over 7 days)
- Browser automation for actions not supported by API
- Safety limits and cooldowns

---

### 5. **Browser Automation**
**Location**: `src/automation/browser/`

**Capabilities**:
- ✅ Playwright-based browser automation
- ✅ Like posts (for actions not supported by API)
- ✅ Follow users
- ✅ View stories
- ✅ Session management
- ✅ Headless browser support

**Features**:
- Browser session persistence
- Automatic login with credentials
- Action execution with retries
- Error handling and recovery

---

### 6. **Safety & Rate Limiting System**
**Location**: `src/safety/`, `src/api/rate_limiter.py`

**Capabilities**:
- ✅ Global rate limiting (requests per hour/minute)
- ✅ Per-account rate limiting
- ✅ Cooldown management between actions
- ✅ Daily activity limits
- ✅ Pattern detection (detects suspicious activity)
- ✅ Risk assessment
- ✅ Health monitoring

**Components**:
- `RateLimiter` - API rate limiting
- `Throttler` - Action throttling
- `CooldownManager` - Cooldown enforcement
- `DailyLimits` - Daily activity limits
- `PatternDetector` - Activity pattern analysis
- `RiskAssessor` - Risk evaluation
- `HealthMonitor` - System health tracking

---

### 7. **Web Dashboard**
**Location**: `web/`

**Capabilities**:
- ✅ Beautiful, modern web interface
- ✅ Post creation and management
- ✅ View published posts
- ✅ Real-time log viewing
- ✅ Configuration management
- ✅ Account status monitoring
- ✅ Comment-to-DM configuration UI
- ✅ Per-post file attachment UI

**Pages**:
- `/` - Post creation page
- `/posts` - Published posts view
- `/logs` - Log viewer
- `/settings` - Configuration management

**Authentication**:
- Password-protected dashboard
- Session management
- Secure API endpoints

---

### 8. **Proxy Support**
**Location**: `src/proxies/proxy_manager.py`

**Capabilities**:
- ✅ Per-account proxy configuration
- ✅ Proxy rotation support
- ✅ Connection timeout handling
- ✅ SSL verification control
- ✅ Automatic retry on proxy failures

**Configuration** (`config/accounts.yaml`):
```yaml
proxy:
  enabled: true
  http: "http://proxy.example.com:8080"
  https: "https://proxy.example.com:8080"
```

---

### 9. **Media Management**
**Location**: `web/cloudinary_helper.py`, `web/api.py`

**Capabilities**:
- ✅ Cloudinary integration for media hosting
- ✅ Automatic image/video upload
- ✅ URL verification before posting
- ✅ Support for multiple media formats
- ✅ Media optimization

**Features**:
- Secure media upload
- Public URL generation
- Media accessibility verification
- Support for images and videos

---

### 10. **Logging & Monitoring**
**Location**: `src/utils/logger.py`

**Capabilities**:
- ✅ Structured JSON logging
- ✅ Log rotation (configurable size and backup count)
- ✅ Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- ✅ File and console logging
- ✅ Real-time log viewing via web dashboard

**Log Features**:
- Comprehensive event logging
- Error tracking
- Performance metrics
- Action history

---

### 11. **Configuration Management**
**Location**: `src/utils/config_loader.py`, `web/api.py`

**Capabilities**:
- ✅ YAML-based configuration
- ✅ Per-account settings
- ✅ Global application settings
- ✅ Runtime configuration updates
- ✅ Configuration validation

**Configuration Files**:
- `config/accounts.yaml` - Account credentials and settings
- `config/settings.yaml` - Application settings
- `config/app_credentials.yaml` - App credentials

**API Endpoints**:
- `GET /api/config/account` - Get account configuration
- `GET /api/config/settings` - Get application settings
- `PUT /api/config/account` - Update account configuration
- `PUT /api/config/settings` - Update application settings

---

### 12. **Scheduler System**
**Location**: `src/core/scheduler.py`

**Capabilities**:
- ✅ Task scheduling
- ✅ Background job execution
- ✅ Comment monitoring scheduling
- ✅ Warming action scheduling
- ✅ Flexible scheduling options

---

### 13. **State Management**
**Location**: `src/core/state_manager.py`

**Capabilities**:
- ✅ Application state persistence
- ✅ Comment tracking state
- ✅ DM tracking state
- ✅ Processed items tracking

---

### 14. **Policy Engine**
**Location**: `src/core/policy_engine.py`

**Capabilities**:
- ✅ Policy-based decision making
- ✅ Action approval/rejection
- ✅ Safety rule enforcement
- ✅ Configurable policies

---

## 📊 API Endpoints Summary

### Authentication
- `POST /api/login` - Login to dashboard
- `POST /api/logout` - Logout
- `GET /api/auth/status` - Check auth status

### Posts
- `POST /api/posts/create` - Create and publish post
- `GET /api/posts` - Get published posts
- `POST /api/posts/{post_id}/publish` - Publish scheduled post
- `POST /api/posts/{media_id}/dm-file` - Attach file to post for DM
- `GET /api/posts/{media_id}/dm-file` - Get post DM file
- `DELETE /api/posts/{media_id}/dm-file` - Remove post DM file

### Comment-to-DM
- `GET /api/comment-to-dm/status` - Get automation status
- `GET /api/comment-to-dm/config` - Get configuration
- `PUT /api/comment-to-dm/config` - Update configuration

### Configuration
- `GET /api/config/account` - Get account config
- `GET /api/config/settings` - Get settings
- `PUT /api/config/account` - Update account config
- `PUT /api/config/settings` - Update settings

### Utilities
- `POST /api/upload` - Upload media file
- `GET /api/verify-url` - Verify media URL
- `GET /api/logs` - Get application logs
- `GET /api/status` - Get system status

---

## 🔧 Technical Features

### Error Handling
- Comprehensive exception handling
- Retry logic with exponential backoff
- Graceful error recovery
- Detailed error logging

### Rate Limiting
- Instagram API rate limit compliance
- Configurable limits per account
- Automatic rate limit detection
- Retry-after handling

### Security
- Password-protected dashboard
- Session management
- Secure token storage
- Proxy support for privacy

### Scalability
- Multi-account support
- Account isolation
- Independent rate limiting per account
- Efficient resource management

---

## 📈 Current Status

### ✅ Fully Implemented
- Automated posting (images, videos, carousels)
- Comment-to-DM automation
- Comment monitoring and auto-reply
- Account warming system
- Web dashboard
- Safety systems
- Rate limiting
- Proxy support
- Media management (Cloudinary)
- Logging and monitoring
- Configuration management

### 🔄 In Progress / Partial
- Browser automation (Playwright integration - optional)
- Like actions via browser (simulated when Playwright not available)

### 📝 Future Enhancements
- Story posting
- Reels posting
- Advanced analytics
- Multi-language support
- Webhook integrations
- Advanced scheduling

---

## 🎯 Use Cases

1. **Content Creators**: Automate posting and engage with audience via auto-DM
2. **Businesses**: Manage multiple Instagram accounts, automate customer engagement
3. **Marketers**: Schedule posts, automate lead generation via comment-to-DM funnel
4. **Agencies**: Manage multiple client accounts from one dashboard

---

## 📚 Documentation

- **[Setup Guide](SETUP.md)** - Initial setup and configuration
- **[Comment-to-DM Setup](COMMENT_TO_DM_SETUP.md)** - Comment-to-DM automation guide
- **[Token Guide](TOKEN_GUIDE.md)** - Instagram token generation
- **[Cloudinary Setup](CLOUDINARY.md)** - Media hosting setup
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and fixes
- **[Architecture](ARCHITECTURE.md)** - System architecture

---

## 🔐 Required Permissions

For full functionality, your Instagram access token needs:
- `instagram_basic` - Basic access
- `instagram_manage_comments` - Read/manage comments
- `instagram_manage_messages` - Send DMs
- `instagram_content_publish` - Publish posts

---

*Last Updated: 2026-01-24*
