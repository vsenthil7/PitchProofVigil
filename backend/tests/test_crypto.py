"""Tests for the crypto package: key provider, cipher, rotation, redaction."""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.crypto.cipher import FieldCipher
from app.crypto.keys import KeyProvider


def test_dev_key_is_ephemeral():
    p = KeyProvider(Settings(jwt_secret="seed"))
    assert p.is_ephemeral is True
    assert p.key_count == 1


def test_configured_keys_not_ephemeral():
    k = KeyProvider.generate_key()
    p = KeyProvider(Settings(jwt_secret="x", encryption_keys=k))
    assert p.is_ephemeral is False
    assert p.key_count == 1


def test_multiple_keys_counted():
    k1, k2 = KeyProvider.generate_key(), KeyProvider.generate_key()
    p = KeyProvider(Settings(jwt_secret="x", encryption_keys=f"{k1},{k2}"))
    assert p.key_count == 2


def test_encrypt_decrypt_roundtrip():
    c = FieldCipher(KeyProvider(Settings(jwt_secret="seed")))
    enc = c.encrypt("secret-value")
    assert c.is_encrypted(enc)
    assert enc != "secret-value"
    assert c.decrypt(enc) == "secret-value"


def test_empty_passthrough():
    c = FieldCipher(KeyProvider(Settings(jwt_secret="seed")))
    assert c.encrypt("") == ""
    assert c.decrypt("") == ""


def test_legacy_plaintext_tolerated():
    c = FieldCipher(KeyProvider(Settings(jwt_secret="seed")))
    # A value without the prefix is returned unchanged (migration path).
    assert c.decrypt("legacy-plain-secret") == "legacy-plain-secret"
    assert c.is_encrypted("legacy-plain-secret") is False


def test_key_rotation_decrypts_old_and_reencrypts():
    k_old = KeyProvider.generate_key()
    k_new = KeyProvider.generate_key()
    old_cipher = FieldCipher(KeyProvider(Settings(jwt_secret="x", encryption_keys=k_old)))
    enc_old = old_cipher.encrypt("rotate-me")

    # Ring with new key first, old key still present → decrypts.
    both = FieldCipher(KeyProvider(Settings(jwt_secret="x", encryption_keys=f"{k_new},{k_old}")))
    assert both.decrypt(enc_old) == "rotate-me"
    rotated = both.rotate(enc_old)

    # New-key-only ring can read the rotated value (old key dropped).
    new_only = FieldCipher(KeyProvider(Settings(jwt_secret="x", encryption_keys=k_new)))
    assert new_only.decrypt(rotated) == "rotate-me"


def test_decrypt_with_wrong_key_raises():
    k1 = KeyProvider.generate_key()
    k2 = KeyProvider.generate_key()
    enc = FieldCipher(KeyProvider(Settings(jwt_secret="x", encryption_keys=k1))).encrypt("v")
    wrong = FieldCipher(KeyProvider(Settings(jwt_secret="x", encryption_keys=k2)))
    with pytest.raises(ValueError):
        wrong.decrypt(enc)


def test_generate_key_is_valid_fernet():
    k = KeyProvider.generate_key()
    # Usable as a real key.
    p = KeyProvider(Settings(jwt_secret="x", encryption_keys=k))
    c = FieldCipher(p)
    assert c.decrypt(c.encrypt("ok")) == "ok"


async def test_webhook_secret_encrypted_at_rest(db, tenant_id):
    """End-to-end: secret stored encrypted, returned decrypted to callers."""
    from app.repositories.audit import WebhookRepository
    from sqlalchemy import select
    from app.db.models import WebhookSubscriptionRow

    cipher = FieldCipher(KeyProvider(Settings(jwt_secret="seed")))
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id, cipher=cipher)
        created = await repo.create("https://hook/x", "gate_decided", "plaintext-secret")
        # Caller gets plaintext back (needed for immediate signing).
        assert created.secret == "plaintext-secret"
    # Raw column is ciphertext.
    async with db.session() as s:
        raw = (await s.execute(select(WebhookSubscriptionRow))).scalars().first()
        assert raw.secret.startswith("enc:v1:")
        assert raw.secret != "plaintext-secret"
    # Read path decrypts transparently.
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id, cipher=cipher)
        hooks = await repo.for_event("gate_decided")
        assert hooks[0].secret == "plaintext-secret"


async def test_webhook_repo_without_cipher_passthrough(db, tenant_id):
    from app.repositories.audit import WebhookRepository

    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)  # no cipher
        created = await repo.create("https://hook/x", "gate_decided", "plain")
        assert created.secret == "plain"
        hooks = await repo.for_event("gate_decided")
        assert hooks[0].secret == "plain"
