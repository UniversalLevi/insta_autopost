"""Cloudflare Tunnel helper for automatic tunnel creation"""

import os
import subprocess
import time
import re
from pathlib import Path
from typing import Optional

# Global Cloudflare tunnel URL
_cloudflare_url: Optional[str] = None
_cloudflare_process: Optional[subprocess.Popen] = None


def start_cloudflare(port: int = 8000) -> Optional[str]:
    """Start Cloudflare tunnel and return the public URL"""
    global _cloudflare_url, _cloudflare_process
    
    try:
        # Start cloudflared tunnel
        cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        _cloudflare_process = process
        
        # Wait for tunnel to start and extract URL
        url = None
        max_wait = 10  # Wait up to 10 seconds
        waited = 0
        
        # Read output line by line
        while waited < max_wait and not url:
            if process.poll() is not None:
                # Process exited, check return code
                if process.returncode != 0:
                    output = process.stdout.read() if process.stdout else ""
                    raise Exception(f"cloudflared exited with code {process.returncode}. Output: {output}")
                break
            
            # Try to read a line (non-blocking)
            line = None
            try:
                if process.stdout:
                    line = process.stdout.readline()
            except Exception:
                pass
            
            if line:
                print(f"cloudflared: {line.strip()}", flush=True)
                # Look for URL in output
                if "https://" in line:
                    # Extract URL from cloudflared output
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        url = match.group(0)
                        break
                    # Alternative format (some versions)
                    match = re.search(r'https://[a-zA-Z0-9-]+\.cfargotunnel\.com', line)
                    if match:
                        url = match.group(0)
                        break
                    # Another possible format
                    match = re.search(r'https://[a-z0-9-]+--[a-z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        url = match.group(0)
                        break
            
            if not url:
                time.sleep(0.5)
                waited += 0.5
        
        if not url:
            # Try one more time to read all output
            if process.stdout:
                remaining = process.stdout.read()
                if remaining:
                    print(f"cloudflared output: {remaining}")
                    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', remaining)
                    if match:
                        url = match.group(0)
            
            if not url:
                raise Exception("Could not extract Cloudflare tunnel URL from output. Make sure cloudflared is installed and working.")
        
        _cloudflare_url = url
        
        print(f"\n{'='*60}")
        print(f"Cloudflare Tunnel started successfully!")
        print(f"Public HTTPS URL: {_cloudflare_url}")
        print(f"Local URL: http://localhost:{port}")
        print(f"{'='*60}\n")
        
        return _cloudflare_url
    
    except FileNotFoundError:
        print("Warning: cloudflared not found. Install it from:")
        print("  https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        print("  Or: choco install cloudflared (Windows) / brew install cloudflared (Mac)")
        print("For now, using localhost URLs (Instagram won't be able to access them)")
        return None
    except Exception as e:
        print(f"Warning: Failed to start Cloudflare tunnel: {e}")
        print("For now, using localhost URLs (Instagram won't be able to access them)")
        if _cloudflare_process:
            try:
                _cloudflare_process.terminate()
            except Exception:
                pass
            _cloudflare_process = None
        return None


def stop_cloudflare():
    """Stop Cloudflare tunnel"""
    global _cloudflare_url, _cloudflare_process
    
    if _cloudflare_process:
        try:
            _cloudflare_process.terminate()
            _cloudflare_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _cloudflare_process.kill()
            _cloudflare_process.wait()
        except Exception as e:
            print(f"Warning: Failed to stop Cloudflare tunnel: {e}")
        finally:
            _cloudflare_process = None
            _cloudflare_url = None
            print("\nCloudflare tunnel stopped.")


def get_cloudflare_url() -> Optional[str]:
    """Get the current Cloudflare tunnel URL"""
    return _cloudflare_url


def get_current_public_base_url() -> str:
    """Return current public base URL for background use (no request). Prefers BASE_URL/APP_URL, then Cloudflare tunnel."""
    base = os.getenv("BASE_URL") or os.getenv("APP_URL")
    if base:
        return (base or "").strip().rstrip("/")
    global _cloudflare_url
    if _cloudflare_url:
        return _cloudflare_url.rstrip("/")
    return ""


def get_base_url(request_base_url: str = "", request_headers=None) -> str:
    """Get base URL for serving uploads. Prefers BASE_URL, then proxy headers, then Cloudflare tunnel, then request."""
    import os

    # 1) Production: use BASE_URL or APP_URL (your public HTTPS domain)
    base = os.getenv("BASE_URL") or os.getenv("APP_URL")
    if base:
        return base.strip().rstrip("/")

    # 2) Behind a proxy (Render, Heroku, nginx): use X-Forwarded-Proto + X-Forwarded-Host
    if request_headers:
        proto = request_headers.get("X-Forwarded-Proto") or request_headers.get("X-Forwarded-Protocol")
        host = request_headers.get("X-Forwarded-Host") or request_headers.get("Host")
        if proto and host:
            return f"{proto.strip()}://{host.split(',')[0].strip()}".rstrip("/")

    # 3) Development: use Cloudflare tunnel if available
    global _cloudflare_url
    if _cloudflare_url:
        return _cloudflare_url.rstrip("/")

    # 4) Fallback: request URL (e.g. http://localhost:8000)
    if request_base_url:
        return str(request_base_url).rstrip("/")
    return ""
