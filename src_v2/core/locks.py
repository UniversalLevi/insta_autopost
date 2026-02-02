"""
V2 per-user locking to prevent race conditions.

Keys: lock:user:{user_id}:posting, lock:user:{user_id}:dm, etc.
Uses file-based locks (no Redis required). Optional Redis can be added later.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DATA_DIR = Path(os.getenv("V2_DATA_DIR", "data"))
LOCKS_DIR = DATA_DIR / "locks_v2"
LOCK_TIMEOUT_SECONDS = 30
LOCK_POLL_INTERVAL = 0.2


def _lock_path(key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    return LOCKS_DIR / f"{safe}.lock"


@contextmanager
def acquire_lock(key: str, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> Generator[None, None, None]:
    """
    Acquire a named lock (e.g. lock:user:{id}:posting).
    File-based; blocks until acquired or timeout.
    """
    path = _lock_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    fd = None
    try:
        while (time.monotonic() - start) < timeout_seconds:
            try:
                fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                fd = None
                yield
                return
            except FileExistsError:
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                    fd = None
                time.sleep(LOCK_POLL_INTERVAL)
        raise TimeoutError(f"Could not acquire lock {key} within {timeout_seconds}s")
    finally:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass


def lock_key_posting(user_id: str, instagram_id: str) -> str:
    return f"lock:user:{user_id}:ig:{instagram_id}:posting"


def lock_key_dm(user_id: str, instagram_id: str) -> str:
    return f"lock:user:{user_id}:ig:{instagram_id}:dm"
