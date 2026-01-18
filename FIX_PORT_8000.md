# Fix: Port 8000 Already in Use

If you see this error:
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

It means another Python server is already running on port 8000.

## Quick Fix Options:

### Option 1: Kill the existing Python process (Recommended)

**In PowerShell, run:**
```powershell
Get-Process python | Stop-Process -Force
```

Then start your server again:
```powershell
python web_server.py
```

### Option 2: Use a different port

**Set a different port:**
```powershell
$env:WEB_PORT = "8001"
python web_server.py
```

Or edit the `.env` file and add:
```
WEB_PORT=8001
```

### Option 3: Find and kill the specific process

**See what's running on port 8000:**
```powershell
netstat -ano | findstr :8000
```

This shows the PID (Process ID) using port 8000.

**Kill that specific process:**
```powershell
taskkill /PID <PID_NUMBER> /F
```

Replace `<PID_NUMBER>` with the number you saw.

## After fixing, start your server:

```powershell
python web_server.py
```
