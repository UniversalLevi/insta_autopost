"""Ngrok helper for automatic tunnel creation"""

import os
from typing import Optional

# Global ngrok URL
_ngrok_url: Optional[str] = None


def start_ngrok(port: int = 8000) -> str:
    """Start ngrok tunnel and return the public URL"""
    global _ngrok_url
    
    try:
        from pyngrok import ngrok, conf
        
        # Get ngrok authtoken from environment first
        authtoken = os.getenv("NGROK_AUTHTOKEN")
        
        # If not in environment, try to read from ngrok config file
        if not authtoken:
            try:
                # Try to find ngrok config file (common locations)
                ngrok_config_paths = [
                    Path.home() / ".ngrok2" / "ngrok.yml",
                    Path.home() / ".ngrok" / "ngrok.yml",
                    Path(os.getenv("APPDATA", "")) / "ngrok" / "ngrok.yml",  # Windows
                ]
                
                for config_path in ngrok_config_paths:
                    if config_path.exists():
                        # Read config file to extract authtoken
                        import yaml
                        with open(config_path, 'r') as f:
                            config = yaml.safe_load(f) or {}
                            if 'authtoken' in config:
                                authtoken = config['authtoken']
                                break
            except Exception:
                pass  # If we can't read config, continue without it
        
        # Set authtoken if we found one
        if authtoken:
            try:
                conf.get_default().auth_token = authtoken
            except Exception as e:
                print(f"Warning: Could not set ngrok authtoken: {e}")
        else:
            print("Warning: No ngrok authtoken found. Set NGROK_AUTHTOKEN environment variable or run: ngrok config add-authtoken YOUR_TOKEN")
            print("Continuing without authtoken (may fail if ngrok requires authentication)...")
        
        # Start ngrok tunnel
        tunnel = ngrok.connect(port, bind_tls=True)  # Use HTTPS
        _ngrok_url = tunnel.public_url
        
        print(f"\n{'='*60}")
        print(f"Ngrok tunnel started successfully!")
        print(f"Public HTTPS URL: {_ngrok_url}")
        print(f"Local URL: http://localhost:{port}")
        print(f"{'='*60}\n")
        
        return _ngrok_url
    
    except ImportError:
        print("Warning: pyngrok not installed. Install it with: pip install pyngrok")
        print("For now, using localhost URLs (Instagram won't be able to access them)")
        return None
    except Exception as e:
        error_msg = str(e)
        if "authtoken" in error_msg.lower() or "authentication" in error_msg.lower():
            print(f"\nError: Ngrok requires an authtoken.")
            print(f"Set it as an environment variable:")
            print(f"  Windows: set NGROK_AUTHTOKEN=your_token_here")
            print(f"  Linux/Mac: export NGROK_AUTHTOKEN=your_token_here")
            print(f"Or get your token from: https://dashboard.ngrok.com/get-started/your-authtoken\n")
        else:
            print(f"Warning: Failed to start ngrok: {e}")
        print("For now, using localhost URLs (Instagram won't be able to access them)")
        return None


def stop_ngrok():
    """Stop ngrok tunnel"""
    global _ngrok_url
    
    try:
        from pyngrok import ngrok
        ngrok.kill()
        _ngrok_url = None
        print("\nNgrok tunnel stopped.")
    except Exception as e:
        print(f"Warning: Failed to stop ngrok: {e}")


def get_ngrok_url() -> Optional[str]:
    """Get the current ngrok URL"""
    return _ngrok_url


def get_base_url(request_base_url: str) -> str:
    """Get base URL, preferring ngrok URL if available"""
    global _ngrok_url
    
    if _ngrok_url:
        return _ngrok_url.rstrip('/')
    
    return str(request_base_url).rstrip('/')
