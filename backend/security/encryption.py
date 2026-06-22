"""
AES-256-GCM encryption/decryption helpers.

The master key defaults to settings.encryption_key_bytes but can be
passed explicitly — useful for unit tests without mocking the global settings.
"""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, key: bytes | None = None) -> str:
    """
    AES-256-GCM encrypt.

    Args:
        plaintext: Raw string to encrypt.
        key: 32-byte key. Defaults to settings.encryption_key_bytes.

    Returns:
        base64(nonce + ciphertext)
    """
    if key is None:
        from backend.config import settings
        key = settings.encryption_key_bytes
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(ciphertext_b64: str, key: bytes | None = None) -> str:
    """
    AES-256-GCM decrypt.

    Args:
        ciphertext_b64: base64(nonce + ciphertext) as returned by encrypt().
        key: 32-byte key. Defaults to settings.encryption_key_bytes.

    Returns:
        Original plaintext string.
    """
    if key is None:
        from backend.config import settings
        key = settings.encryption_key_bytes
    raw = base64.b64decode(ciphertext_b64)
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
