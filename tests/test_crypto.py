import pytest
import nacl.exceptions

from engine.crypto import (
    encrypt_pii,
    decrypt_pii,
    generate_key,
    purge_encrypted_block,
)


@pytest.fixture
def key() -> bytes:
    return bytes.fromhex(generate_key())


def test_roundtrip(key):
    plaintext = '{"name": "Alice", "email": "alice@example.com", "phone": "+44 7700 900000"}'
    ct = encrypt_pii(plaintext, key=key)
    assert decrypt_pii(ct, key=key) == plaintext


def test_ciphertext_hides_plaintext(key):
    plaintext = "sensitive personal data"
    ct = encrypt_pii(plaintext, key=key)
    assert plaintext not in ct
    assert "sensitive" not in ct


def test_nonce_is_random(key):
    # Same plaintext + same key must produce different ciphertexts (random nonce).
    ct1 = encrypt_pii("same text", key=key)
    ct2 = encrypt_pii("same text", key=key)
    assert ct1 != ct2


def test_wrong_key_raises(key):
    other_key = bytes.fromhex(generate_key())
    ct = encrypt_pii("secret", key=key)
    with pytest.raises(nacl.exceptions.CryptoError):
        decrypt_pii(ct, key=other_key)


def test_tampered_ciphertext_raises(key):
    import base64

    ct = encrypt_pii("secret", key=key)
    raw = bytearray(base64.b64decode(ct))
    raw[-1] ^= 0xFF  # flip a bit
    corrupted = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(nacl.exceptions.CryptoError):
        decrypt_pii(corrupted, key=key)


def test_purge_returns_same_encoded_length(key):
    ct = encrypt_pii("Alice Smith, 42 Elm St", key=key)
    zeroed = purge_encrypted_block(ct)
    assert len(zeroed) == len(ct)


def test_purge_decodes_to_zeros(key):
    import base64

    ct = encrypt_pii("Alice Smith", key=key)
    zeroed = purge_encrypted_block(ct)
    decoded = base64.b64decode(zeroed)
    assert all(b == 0 for b in decoded)


def test_generate_key_is_32_bytes():
    key_hex = generate_key()
    assert len(bytes.fromhex(key_hex)) == 32


def test_generate_key_unique():
    assert generate_key() != generate_key()


def test_missing_env_key_raises(monkeypatch):
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="PII_ENCRYPTION_KEY"):
        encrypt_pii("data")


def test_wrong_length_env_key_raises(monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "deadbeef")  # 4 bytes, not 32
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_pii("data")
