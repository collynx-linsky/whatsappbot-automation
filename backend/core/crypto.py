"""
WhatsAppBusinessAI — Secret Encryption Helper

Symmetric encryption (Fernet/AES) for credentials that must be stored at
rest but never returned via any API response — WhatsApp access tokens
today, any future third-party API secret stored per-tenant. Never use this
for passwords (those are hashed, not encrypted, via Django's auth system).
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    # Deliberately not cached: Fernet(key) is cheap (a base64 decode + a
    # validation check), and caching it would serve a stale key if
    # settings.WHATSAPP_TOKEN_ENCRYPTION_KEY ever changes within a process
    # — which pytest's `settings` fixture does routinely between tests.
    key = getattr(settings, "WHATSAPP_TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured(
            "WHATSAPP_TOKEN_ENCRYPTION_KEY is not set. Generate one with "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and put it in .env.'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypts a string for storage; returns an opaque token string."""
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypts a token previously produced by encrypt_secret. Raises InvalidToken if tampered/wrong key."""
    if not token:
        return ""
    return _fernet().decrypt(token.encode()).decode()


__all__ = ["encrypt_secret", "decrypt_secret", "InvalidToken"]
