"""Tests for auth_service: password hashing, verification, JWT creation/decoding."""
from __future__ import annotations

import time

import pytest

from app.services.auth_service import (
    create_access_token,
    get_password_hash,
    verify_password,
)


# ── Password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_different_from_plaintext(self):
        hashed = get_password_hash("mysecretpassword")
        assert hashed != "mysecretpassword"

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = get_password_hash("mysecretpassword")
        assert hashed.startswith("$2")

    def test_different_calls_produce_different_hashes(self):
        """bcrypt uses random salt, so two calls must differ."""
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password_verifies(self):
        hashed = get_password_hash("correct_horse")
        assert verify_password("correct_horse", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = get_password_hash("correct_horse")
        assert verify_password("wrong_password", hashed) is False

    def test_empty_string_does_not_verify_against_real_hash(self):
        hashed = get_password_hash("notempty")
        assert verify_password("", hashed) is False


# ── JWT creation / decoding ───────────────────────────────────────────────────

class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(subject="alice", role="viewer")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_decodes_to_correct_subject_and_role(self):
        import jwt as pyjwt
        from app.config import get_settings

        settings = get_settings()
        token = create_access_token(subject="bob", role="admin")
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        assert payload["sub"] == "bob"
        assert payload["role"] == "admin"

    def test_token_contains_expiry(self):
        import jwt as pyjwt
        from app.config import get_settings

        settings = get_settings()
        token = create_access_token(subject="charlie", role="viewer")
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        assert "exp" in payload

    def test_token_expires_in_future(self):
        import jwt as pyjwt
        from app.config import get_settings

        settings = get_settings()
        token = create_access_token(subject="dave", role="viewer")
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        assert payload["exp"] > time.time()

    def test_different_subjects_produce_different_tokens(self):
        t1 = create_access_token(subject="user1", role="viewer")
        t2 = create_access_token(subject="user2", role="viewer")
        assert t1 != t2
