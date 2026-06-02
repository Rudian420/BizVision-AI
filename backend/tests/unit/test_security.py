"""Offline unit tests for the security primitives — no services required."""

from __future__ import annotations

import pytest

from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-123", extra_claims={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["role"] == "admin"


def test_refresh_token_type():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_decode_rejects_garbage():
    from jose import JWTError

    with pytest.raises(JWTError):
        decode_token("not-a-real-token")
