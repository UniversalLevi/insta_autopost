# 🚀 Quick Deployment Guide

Choose your deployment platform and follow the steps below.

## Option 1: Docker (Recommended for VPS/Servers)

### Quick Start:
```powershell
# Windows
.\scripts\deploy_docker.ps1

# Or manually:
docker-compose up -d
```

**Access:** http://localhost:8000

---

## Option 2: Railway (Easiest Cloud Deployment)

### Prerequisites:
1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`

### Deploy:
```powershell
.\scripts\deploy_railway.ps1
```

Or manually:
```bash
railway init
railway up
railway domain  # Get your URL
```

**Set Environment Variables in Railway Dashboard:**
- `META_APP_ID`
- `META_APP_SECRET`
- `OPENAI_API_KEY`
- `WEBHOOK_VERIFY_TOKEN`
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

---

## Option 3: Render (Git-Based Deployment)

1. **Connect Repository:**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub/GitLab repo

2. **Auto-Configuration:**
   - Render will detect `render.yaml` automatically
   - Or use these settings:
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python web_server.py`

3. **Set Environment Variables** in Render Dashboard

4. **Deploy:**
   - Render auto-deploys on git push
   - Or click "Manual Deploy"

---

## Option 4: Fly.io

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create and deploy
fly launch
fly secrets set META_APP_ID=your_app_id
fly secrets set META_APP_SECRET=your_secret
# ... set all other variables
fly deploy
```

---

## ⚙️ Required Environment Variables

Set these in your deployment platform:

```bash
# Meta/Instagram
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret

# OpenAI (for AI DM)
OPENAI_API_KEY=your_openai_key

# Webhook
WEBHOOK_VERIFY_TOKEN=my_test_token_for_instagram_verification

# Cloudinary (recommended for media)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Optional
WEB_PASSWORD=admin  # Dashboard password
ENVIRONMENT=production
WEB_PORT=8000
WEB_HOST=0.0.0.0
```

---

## 🔗 After Deployment

1. **Get your deployment URL** (e.g., `https://your-app.railway.app`)

2. **Update Meta Webhook:**
   - Go to [Meta App Dashboard](https://developers.facebook.com/apps/)
   - Navigate to: Webhooks → Instagram
   - Set **Callback URL:** `https://your-url/webhooks/instagram`
   - Set **Verify Token:** Your `WEBHOOK_VERIFY_TOKEN` value
   - Click "Verify and Save"

3. **Test Webhook:**
   - Click "Test" in Meta Dashboard
   - Check your deployment logs for webhook events

4. **Access Dashboard:**
   - Visit: `https://your-url`
   - Login: `admin` / `admin` (or your `WEB_PASSWORD`)

---

## 📚 Full Documentation

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions for each platform.

---

## 🆘 Troubleshooting

### Webhook Not Working?
1. Verify URL is publicly accessible
2. Check verify token matches
3. Check deployment logs
4. Test with: `curl https://your-url/webhooks/instagram?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test`

### Application Won't Start?
1. Check all environment variables are set
2. Check logs: `docker logs instaforge` or platform logs
3. Verify Python version (3.8+)

### Need Help?
- Check [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed troubleshooting
- Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for general issues
