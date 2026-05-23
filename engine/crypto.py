"""
PII encryption using libsodium (via PyNaCl) SecretBox.

Keys live in repo secrets as hex-encoded 32-byte values and are never written
to issue bodies, labels, or comments. Every encrypt call uses a fresh random
nonce so identical plaintexts produce distinct ciphertexts.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

import nacl.exceptions
import nacl.secret
import nacl.utils


def _load_key() -> bytes:
    raw = os.environ.get("PII_ENCRYPTION_KEY", "")
    if not raw:
        raise EnvironmentError("PII_ENCRYPTION_KEY is not set")
    key_bytes = bytes.fromhex(raw)
    if len(key_bytes) != nacl.secret.SecretBox.KEY_SIZE:
        raise ValueError(
            f"PII_ENCRYPTION_KEY must be {nacl.secret.SecretBox.KEY_SIZE} bytes "
            f"({nacl.secret.SecretBox.KEY_SIZE * 2} hex chars)"
        )
    return key_bytes


def encrypt_pii(plaintext: str, *, key: Optional[bytes] = None) -> str:
    """Encrypt a UTF-8 string; return a base64-encoded ciphertext."""
    if key is None:
        key = _load_key()
    box = nacl.secret.SecretBox(key)
    encrypted = box.encrypt(plaintext.encode())
    return base64.b64encode(encrypted).decode()


def decrypt_pii(ciphertext: str, *, key: Optional[bytes] = None) -> str:
    """Decrypt a base64 ciphertext produced by encrypt_pii."""
    if key is None:
        key = _load_key()
    box = nacl.secret.SecretBox(key)
    raw = base64.b64decode(ciphertext)
    return box.decrypt(raw).decode()


def generate_key() -> str:
    """Return a new random 32-byte key as a hex string. For setup / rotation only."""
    return nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE).hex()


def purge_encrypted_block(ciphertext: str) -> str:
    """
    Replace ciphertext with a zero-filled block of the same encoded length.
    Used by the /abort purge flow to overwrite PII in issue bodies.
    """
    decoded_len = len(base64.b64decode(ciphertext))
    return base64.b64encode(bytes(decoded_len)).decode()
