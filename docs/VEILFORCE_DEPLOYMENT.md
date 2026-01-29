# Why the Server Is Not Running on veilforce.com (and How to Fix It)

This doc explains why `https://veilforce.com` may return 404 for `/uploads/` or the dashboard, and how to get the InstaForge app running on your domain.

---

## What “server not running” usually means

When you see:

- **404** for `https://veilforce.com/uploads/...` (with Apache in response headers), or  
- **Dashboard not loading** at `https://veilforce.com`,

it usually means one of:

1. **The InstaForge app process is not running** on the machine that serves veilforce.com.
2. **Apache (or nginx) is not proxying** requests to the InstaForge app, so only Apache responds and returns 404 for paths the app would handle.

The app serves:

- `/` – dashboard (HTML)
- `/uploads/{path}` – uploaded media (images/videos for Instagram)
- `/webhooks/instagram` – Instagram webhook
- `/api/*`, `/auth/*`, etc.

If the **Python app is not running** or **not behind the web server**, only Apache answers, and you get 404 (or default Apache page) for those paths.

---

## Fix: Run InstaForge and proxy veilforce.com to it

### 1. Run the InstaForge app on the server

On the machine that hosts veilforce.com (same box as Apache, or a reachable host):

```bash
cd /path/to/InstaForge
export BASE_URL=https://veilforce.com
export WEB_HOST=127.0.0.1   # or 0.0.0.0 if needed
export WEB_PORT=8000
python web_server.py
```

Or run it as a service (systemd) so it restarts on reboot:

- **Working directory:** your InstaForge repo (so `uploads/` and `data/` exist).
- **Environment:** set `BASE_URL=https://veilforce.com` and any other env vars (e.g. `META_APP_ID`, `META_APP_SECRET`, `WEB_PASSWORD`).
- **Command:** `python web_server.py` (or `python main.py` if you prefer that entry point).

The app must be listening on a port (e.g. 8000) that Apache will proxy to.

### 2. Configure Apache to proxy veilforce.com to the app

Apache must send **all** traffic for veilforce.com (or the relevant vhost) to the InstaForge app. If `/uploads/` is not proxied, you get 404 from Apache.

Example for **mod_proxy** (enable `proxy`, `proxy_http`, `proxy_wstunnel` if you use WebSockets later):

```apache
# VirtualHost for veilforce.com
<VirtualHost *:443>
    ServerName veilforce.com
    # ... SSL config (SSLEngine, certificates, etc.) ...

    # Proxy everything to the InstaForge app
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    # If you only proxy certain paths (not recommended; easy to miss /uploads/):
    # ProxyPass /uploads/ http://127.0.0.1:8000/uploads/
    # ProxyPassReverse /uploads/ http://127.0.0.1:8000/uploads/
    # ProxyPass / http://127.0.0.1:8000/
    # ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

Then:

```bash
sudo a2enmod proxy proxy_http
sudo systemctl reload apache2
```

After this, `https://veilforce.com/` should show the dashboard and `https://veilforce.com/uploads/...` should serve files (if they exist under `uploads/`).

### 3. Set BASE_URL on the server

In the environment of the InstaForge process (systemd unit, `.env`, or shell):

```bash
export BASE_URL=https://veilforce.com
```

So that:

- Upload URLs and webhook callback URL use `https://veilforce.com`.
- Instagram can reach media at `https://veilforce.com/uploads/...`.

---

## Quick checklist

| Check | Action |
|-------|--------|
| InstaForge process running? | `ps aux \| grep web_server` or `systemctl status instaforge` (or your service name). |
| App listens on 8000? | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health` → expect 200. |
| Apache proxies to 8000? | Config has `ProxyPass / http://127.0.0.1:8000/` (and ProxyPassReverse) for veilforce.com. |
| BASE_URL set? | `BASE_URL=https://veilforce.com` in the app’s environment. |
| uploads/ writable? | App can create `uploads/` and `uploads/batch/`; batch uploads go there. |

---

## If you host on Render (or similar) and use veilforce.com as custom domain

- Point **veilforce.com** (DNS) to the Render URL or the IP they give for the custom domain.
- In Render, set **BASE_URL=https://veilforce.com**.
- Then the app will generate `https://veilforce.com/uploads/...` and `https://veilforce.com/webhooks/instagram`; Render serves the app, so no Apache proxy on your side.

---

## Why you saw 404 for `/uploads/...` in logs

Logs showed:

- `https://veilforce.com/uploads/batch/.../day_06.jpg` → **404**, `Content-Type: text/html`, **Server: Apache/2.4.63**.

So the request was answered by **Apache**, not by the InstaForge app. That means either the app was not running on that host or Apache was not proxying `/uploads/` (and the rest of the site) to the app. Fixing the two items above (run app + proxy to it, set BASE_URL) resolves “server not running on veilforce.com” for your own server.

---

## "Proxy Error" / "Error reading from remote server"

When you see:

- **"The proxy server received an invalid response from an upstream server"**
- **"The proxy server could not handle the request"**
- **"Reason: Error reading from remote server"**
- **Server: Apache/2.4.63 (Ubuntu) at veilforce.com Port 443**

Apache is proxying to the InstaForge app, but the **upstream (the app) is not responding correctly**. Common causes:

| Cause | What to do |
|-------|------------|
| **App not running** | Start the app: `python web_server.py` (or your systemd service). Check: `ps aux \| grep web_server` or `systemctl status instaforge`. |
| **App crashed on startup** | Run the app in the foreground and check for Python errors (missing deps, env vars, import errors). Fix and restart. |
| **Wrong port** | App must listen on the same port Apache proxies to (e.g. 8000). Check `WEB_PORT` and Apache `ProxyPass` (e.g. `http://127.0.0.1:8000/`). |
| **App binding to wrong host** | Use `WEB_HOST=0.0.0.0` or `127.0.0.1` so Apache can connect. If the app binds only to another interface, the proxy will fail. |
| **Timeout / slow startup** | App may be starting slowly (DB, APIs). Increase Apache timeout: `ProxyTimeout 300` in the vhost, or fix app startup. |
| **Connection refused** | Nothing is listening on the backend port. Start the app and ensure it listens on that port. |

### Check from the server (SSH)

Run these on the machine that runs Apache (veilforce.com):

```bash
# 1. Is the app process running?
ps aux | grep web_server

# 2. Is anything listening on port 8000?
ss -tlnp | grep 8000
# or: netstat -tlnp | grep 8000

# 3. Can we get a valid response from the app locally?
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health
# Expect: 200

# 4. If 200, the app is fine and Apache can be fixed (timeout, config). If connection refused, start the app.
```

### Apache timeout (if app is slow)

If the app is running but responses are slow, add to your vhost:

```apache
ProxyPass / http://127.0.0.1:8000/
ProxyPassReverse / http://127.0.0.1:8000/
ProxyTimeout 300
```

Then: `sudo systemctl reload apache2`.
