"""
V2 configuration helpers.

This module is intentionally minimal and side-effect free so it can be
imported safely from both legacy (v1) and future (v2) entrypoints.
"""

import os


def is_v2_enabled() -> bool:
    """
    Return True when V2 Safe Mode is enabled via environment.

    Uses USE_V2 env var, matching the project convention:
        - "true" (case-insensitive) -> enabled
        - anything else / unset     -> disabled
    """
    return (os.getenv("USE_V2") or "").strip().lower() == "true"

