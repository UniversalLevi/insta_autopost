# InstaForge Deployment Guide

This guide covers deploying InstaForge to various platforms.

## 📋 Prerequisites

Before deploying, ensure you have:

1. **Environment Variables** configured:
   - `META_APP_ID` - Your Meta App ID
   - `META_APP_SECRET` - Your Meta App Secret
   - `OPENAI_API_KEY` - OpenAI API key (for AI DM features)
   - `WEBHOOK_VERIFY_TOKEN` - Webhook verification token (default: `my_test_token_for_instagram_verification`)
   - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` - For media uploads (recommended)
   - `WEB_PASSWORD` - Dashboard password (optional, defaults to `admin`)

2. **Account Configuration**: Your `data/accounts.yaml` file with Instagram account credentials

3. **Webhook URL**: A publicly accessible URL for Instagram webhooks (e.g., `https://yourdomain.com/webhooks/instagram`)

---

## 🐳 Docker Deployment

### Local Docker Deployment

1. **Build the image:**
   ```bash
   docker build -t instaforge .
   ```

2. **Run with docker-compose:**
   ```bash
   docker-compose up -d
   ```

3. **Or run directly:**
   ```bash
   docker run -d \
     --name instaforge \
     -p 8000:8000 \
     --env-file .env \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/logs:/app/logs \
     -v $(pwd)/config:/app/config \
     instaforge
   ```

### Production Docker Deployment

For production, use a reverse proxy (nginx, Caddy, Traefik) in front of the container:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  instaforge:
    build: .
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - WEB_PORT=8000
      - WEB_HOST=0.0.0.0
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    networks:
      - instaforge-network

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - instaforge
    networks:
      - instaforge-network

networks:
  instaforge-network:
    driver: bridge
```

---

## 🚂 Railway Deployment

Railway automatically detects the `railway.json` configuration.

### Steps:

1. **Install Railway CLI:**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login:**
   ```bash
   railway login
   ```

3. **Initialize project:**
   ```bash
   railway init
   ```

4. **Set environment variables:**
   ```bash
   railway variables set META_APP_ID=your_app_id
   railway variables set META_APP_SECRET=your_app_secret
   railway variables set OPENAI_API_KEY=your_openai_key
   railway variables set WEBHOOK_VERIFY_TOKEN=your_verify_token
   # ... add all other variables
   ```

5. **Deploy:**
   ```bash
   railway up
   ```

6. **Get your URL:**
   ```bash
   railway domain
   ```

7. **Update Meta Webhook:**
   - Go to Meta App Dashboard → Webhooks
   - Set Callback URL: `https://your-railway-url.railway.app/webhooks/instagram`
   - Set Verify Token: Your `WEBHOOK_VERIFY_TOKEN` value

---

## 🎨 Render Deployment

Render automatically detects the `render.yaml` configuration.

### Steps:

1. **Connect Repository:**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub/GitLab repository

2. **Configure Service:**
   - Render will auto-detect `render.yaml`
   - Or manually configure:
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python web_server.py`
     - **Environment:** Python 3

3. **Set Environment Variables:**
   In Render Dashboard → Environment:
   ```
   ENVIRONMENT=production
   WEB_PORT=8000
   WEB_HOST=0.0.0.0
   META_APP_ID=your_app_id
   META_APP_SECRET=your_app_secret
   OPENAI_API_KEY=your_openai_key
   WEBHOOK_VERIFY_TOKEN=your_verify_token
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

4. **Deploy:**
   - Render will automatically deploy on git push
   - Or click "Manual Deploy" in dashboard

5. **Update Meta Webhook:**
   - Your Render URL: `https://your-service.onrender.com`
   - Set Callback URL: `https://your-service.onrender.com/webhooks/instagram`
   - Set Verify Token: Your `WEBHOOK_VERIFY_TOKEN` value

---

## ☁️ Fly.io Deployment

1. **Install Fly CLI:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login:**
   ```bash
   fly auth login
   ```

3. **Create app:**
   ```bash
   fly launch
   ```

4. **Set secrets (environment variables):**
   ```bash
   fly secrets set META_APP_ID=your_app_id
   fly secrets set META_APP_SECRET=your_app_secret
   fly secrets set OPENAI_API_KEY=your_openai_key
   fly secrets set WEBHOOK_VERIFY_TOKEN=your_verify_token
   ```

5. **Deploy:**
   ```bash
   fly deploy
   ```

6. **Get URL:**
   ```bash
   fly info
   ```

---

## 🐧 VPS/Server Deployment

### Using systemd (Linux)

1. **Create service file** `/etc/systemd/system/instaforge.service`:

```ini
[Unit]
Description=InstaForge Instagram Automation
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/InstaForge
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python web_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. **Enable and start:**
   ```bash
   sudo systemctl enable instaforge
   sudo systemctl start instaforge
   sudo systemctl status instaforge
   ```

### Using Nginx Reverse Proxy

Create `/etc/nginx/sites-available/instaforge`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/instaforge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 🔧 Post-Deployment Checklist

After deploying, verify:

- [ ] Application is accessible at your domain
- [ ] Health endpoint works: `https://yourdomain.com/api/health`
- [ ] Webhook endpoint is accessible: `https://yourdomain.com/webhooks/instagram`
- [ ] Meta webhook is configured with correct URL and verify token
- [ ] Test webhook from Meta Dashboard
- [ ] Check logs for any errors
- [ ] Verify environment variables are set correctly
- [ ] Test posting a media file
- [ ] Test webhook receiving (send a test message/comment)

---

## 🐛 Troubleshooting

### Webhook Not Receiving Events

1. **Check webhook URL is publicly accessible:**
   ```bash
   curl https://yourdomain.com/webhooks/instagram?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test
   ```
   Should return: `test`

2. **Check server logs:**
   ```bash
   # Docker
   docker logs instaforge
   
   # Systemd
   journalctl -u instaforge -f
   ```

3. **Verify Meta Dashboard:**
   - Go to Meta App Dashboard → Webhooks
   - Check subscription status
   - Click "Test" button

### Application Won't Start

1. **Check environment variables:**
   ```bash
   # Docker
   docker exec instaforge env | grep META
   
   # Systemd
   systemctl show instaforge | grep Environment
   ```

2. **Check logs:**
   ```bash
   tail -f logs/instaforge.log
   ```

3. **Verify Python version:**
   ```bash
   python --version  # Should be 3.8+
   ```

### Port Already in Use

Change the port in `.env`:
```
WEB_PORT=8001
```

Or in docker-compose.yml:
```yaml
ports:
  - "8001:8000"
```

---

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Railway Documentation](https://docs.railway.app/)
- [Render Documentation](https://render.com/docs)
- [Fly.io Documentation](https://fly.io/docs/)
- [Nginx Documentation](https://nginx.org/en/docs/)

---

## 🔒 Security Notes

1. **Never commit `.env` file** - It contains sensitive credentials
2. **Use strong passwords** - Set `WEB_PASSWORD` to a secure value
3. **Enable HTTPS** - Always use SSL/TLS in production
4. **Restrict access** - Consider IP whitelisting for admin dashboard
5. **Rotate tokens** - Regularly rotate API keys and tokens
6. **Monitor logs** - Check logs regularly for suspicious activity

---

## 💡 Tips

- **Use Cloudinary** for media uploads instead of Cloudflare tunnel (more reliable)
- **Set up monitoring** - Use services like UptimeRobot to monitor your deployment
- **Backup data** - Regularly backup `data/` directory
- **Use process managers** - PM2, supervisor, or systemd for production
- **Enable auto-restart** - Configure your deployment to auto-restart on failure
