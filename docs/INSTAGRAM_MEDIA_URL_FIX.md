# Instagram Media URL Fix (Error 100/2207067)

This document describes fixes applied to resolve:
**"Instagram cannot access the media URL (error 100/2207067)"**

## Root Cause

Instagram's crawler fetches media from your URL when you post. It requires:

1. **Byte-range support (Range header)** – MP4 streaming uses partial content requests
2. **Correct MIME type** – `video/mp4` for .mp4, `image/jpeg` for .jpg
3. **Public access** – No auth, no cookies, no redirects
4. **CORS** – `Access-Control-Allow-Origin: *`
5. **HTTPS** – Valid SSL certificate

## What Was Fixed

### 1. Byte-Range Support (CRITICAL for MP4)

**File:** `web/main.py`

- Added `_parse_range_header()` to parse `Range: bytes=start-end`
- `/uploads/` route now returns `206 Partial Content` when Range is present
- Instagram's crawler sends Range requests for video; previously we always returned full file

### 2. Absolute Uploads Path

**Files:** `web/main.py`, `web/api.py`, `src/services/batch_upload_service.py`

- `uploads_path` is now `Path(__file__).parent.parent / "uploads"` (project root)
- Prevents CWD-dependent path issues on Render, systemd, Apache proxy

### 3. BASE_URL and APP_URL

**File:** `.env`

- Added `APP_URL=https://veilforce.com` (alias for BASE_URL)
- Both are used by `get_base_url()` for upload URLs

### 4. CORS Headers

**File:** `web/main.py`

- `Access-Control-Allow-Headers` now includes `Range` for preflight
- `Access-Control-Allow-Origin: *` already present for `/uploads/`

### 5. MIME Types

- `video/mp4` for .mp4 and .mov (unchanged, was correct)
- `image/jpeg`, `image/png`, etc. (unchanged)

### 6. Server Configs (Apache/Nginx)

**Files:** `deploy/apache-veilforce.conf`, `deploy/nginx-veilforce.conf`

- Proxy `/uploads/` to FastAPI (no static file serving by web server)
- `ProxyTimeout` / `proxy_read_timeout` 300s for large videos
- Nginx: `proxy_set_header Range $http_range` so upstream receives Range
- No bot blocking (do not block `facebookexternalhit`, `Facebot`)

### 7. File Permissions Script

**File:** `deploy/fix-upload-permissions.sh`

- Sets directories to 755, files to 644
- Run after deploy: `./deploy/fix-upload-permissions.sh`

## Deployment Checklist

1. **Environment**
   - `BASE_URL=https://veilforce.com`
   - `APP_URL=https://veilforce.com`

2. **Apache** (if using Apache)
   - `ProxyPass / http://127.0.0.1:8000/`
   - `ProxyTimeout 300`
   - Reload: `sudo systemctl reload apache2`

3. **Nginx** (if using Nginx)
   - Use `deploy/nginx-veilforce.conf`
   - Ensure Range header is passed: `proxy_set_header Range $http_range`

4. **Permissions**
   - Run `./deploy/fix-upload-permissions.sh`

5. **Verify**
   - `curl -I "https://veilforce.com/uploads/590d8cf8-3b22-4ec2-9605-ee23734d5cb8.mp4"`
   - Expect: `200` or `206`, `Content-Type: video/mp4`, `Accept-Ranges: bytes`
   - Test Range: `curl -H "Range: bytes=0-1023" -I "https://veilforce.com/uploads/xxx.mp4"` → expect `206`

6. **Restart App**
   - `systemctl restart instaforge` (or your service name)
   - Or restart `python web_server.py`

## What Cannot Be Fixed Automatically

- **SSL/HTTPS**: Ensure valid certificate (e.g. Let's Encrypt). If you use Render, they provide SSL.
- **Firewall**: Ensure port 443 is open and not blocking Meta’s IPs.
- **Cloudflare / WAF**: If you use Cloudflare in front, ensure it does not block `facebookexternalhit` or `Facebot`.
- **File existence**: The file `590d8cf8-3b22-4ec2-9605-ee23734d5cb8.mp4` must exist under `uploads/`. If it was never uploaded or was deleted, re-upload.
