import json

import pytest
from cryptography.fernet import Fernet

from app.google_workspace import _decrypt_tokens, _encrypt_tokens, _session_id


def test_workspace_tokens_are_encrypted_and_round_trip():
    key = Fernet.generate_key().decode("ascii")
    tokens = {"access_token": "example-access", "refresh_token": "example-refresh", "expires_at": 123}
    encrypted = _encrypt_tokens(tokens, key)
    assert "example-access" not in encrypted
    assert "example-refresh" not in encrypted
    assert _decrypt_tokens(encrypted, key) == tokens


def test_workspace_tokens_fail_closed_with_wrong_encryption_key():
    key = Fernet.generate_key().decode("ascii")
    wrong_key = Fernet.generate_key().decode("ascii")
    encrypted = _encrypt_tokens({"access_token": "secret"}, key)
    with pytest.raises(Exception):
        _decrypt_tokens(encrypted, wrong_key)


def test_google_session_id_is_created_only_when_requested():
    class FakeRequest:
        def __init__(self):
            self.session = {}

    request = FakeRequest()
    assert _session_id(request) is None
    created = _session_id(request, create=True)
    assert isinstance(created, str) and len(created) >= 32
    assert _session_id(request) == created
