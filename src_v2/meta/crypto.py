"""
V2 crypto helpers for secure storage of Meta tokens.

Uses Fernet (symmetric AES + HMAC) via the cryptography library.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from .config import load_meta_config


def _get_fernet() -> Fernet:
    cfg = load_meta_config()
    return Fernet(cfg.enc_key)


def encrypt_token(plain: str) -> str:
    """Encrypt a token string for persistent storage."""
    f = _get_fernet()
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a previously encrypted token."""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Invalid encryption token")

