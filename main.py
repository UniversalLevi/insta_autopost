import uvicorn
import os
import sys
import signal
import traceback
from pathlib import Path

# Load .env before reading PORT/HOST/ENVIRONMENT
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


def _unhandled_exception(exc_type, exc_value, exc_tb):
    """Log unhandled exceptions so PM2 logs show the cause before restart."""
    if exc_type is KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    msg = "".join(lines)
    print("Unhandled exception (process will exit; PM2 will restart):\n" + msg, file=sys.stderr, flush=True)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


if __name__ == "__main__":
    """
    Entry point for InstaForge.
    Starts the web dashboard and background services.
    """
    # Ensure the current directory is in sys.path so imports work correctly
    root_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root_dir)

    # Log unhandled exceptions so PM2 err log has the traceback before restart
    sys.excepthook = _unhandled_exception

    # Production configuration from environment
    PORT = int(os.getenv("PORT", "8000"))
    HOST = os.getenv("HOST", "127.0.0.1")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    RELOAD = ENVIRONMENT == "development"
    WORKERS = int(os.getenv("WORKERS", "1")) if ENVIRONMENT == "production" else 1

    # Ensure logs dir exists for PM2 (ecosystem.config.cjs writes out/err here)
    if ENVIRONMENT == "production":
        (Path(root_dir) / "logs").mkdir(exist_ok=True)

    print(f"Starting InstaForge from {root_dir}...")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Access the dashboard at http://{HOST}:{PORT}")
    print("Press CTRL+C to stop the server")

    # Handle graceful shutdown on SIGINT (Ctrl+C) and SIGTERM
    def signal_handler(sig, frame):
        print("\n\nShutdown signal received. Stopping server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Run the FastAPI app
        # web.main:app initializes the InstaForgeApp and starts background services on startup
        if ENVIRONMENT == "production" and WORKERS > 1:
            uvicorn.run("web.main:app", host=HOST, port=PORT, workers=WORKERS, log_level="info")
        else:
            uvicorn.run(
                "web.main:app",
                host=HOST,
                port=PORT,
                reload=RELOAD,
                log_level="info" if ENVIRONMENT == "production" else "debug",
            )
    except KeyboardInterrupt:
        print("\n\nShutdown complete.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
