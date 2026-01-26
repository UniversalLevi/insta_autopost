"""Production entry point for InstaForge using uvicorn workers"""

import uvicorn
import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, use system env vars

if __name__ == "__main__":
    # Ensure the current directory is in sys.path so imports work correctly
    root_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root_dir)
    
    # Production configuration from environment
    PORT = int(os.getenv("PORT", "8001"))  # Default to 8001 to avoid conflicts
    HOST = os.getenv("HOST", "127.0.0.1")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
    WORKERS = int(os.getenv("WORKERS", "2"))
    
    print(f"Starting InstaForge in {ENVIRONMENT} mode...")
    print(f"Host: {HOST}, Port: {PORT}, Workers: {WORKERS}")
    
    # Run the FastAPI app with uvicorn workers
    uvicorn.run(
        "web.main:app",
        host=HOST,
        port=PORT,
        workers=WORKERS if ENVIRONMENT == "production" else 1,
        log_level="info",
        access_log=True,
    )
