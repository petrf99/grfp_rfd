import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import hashlib

from rfd.connections_manager import token_manager


# === Tests for hash_token ===

def test_hash_token_returns_uppercase_sha256():
    # Given
    token = "secret_token"
    expected_hash = hashlib.sha256(token.encode()).hexdigest().upper()

    # When
    result = token_manager.hash_token(token)

    # Then
    assert result == expected_hash


# === Tests for create_tailscale_auth_key ===

@patch("rfd.connections_manager.token_manager.requests.post")
def test_create_tailscale_auth_key_success(mock_post):
    # Mock a successful response from Tailscale API
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "tskey-abc123xyz"}
    mock_post.return_value = mock_response

    # When
    key, exp = token_manager.create_tailscale_auth_key("device1", "gcs", expiry_hours=2)

    # Then
    assert key == "tskey-abc123xyz"
    assert exp == 2
    mock_post.assert_called_once()


@patch("rfd.connections_manager.token_manager.requests.post")
def test_create_tailscale_auth_key_failure(mock_post):
    # Mock a failed response from Tailscale API
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Unauthorized"
    mock_post.return_value = mock_response

    # Then: Expect a RuntimeError to be raised
    with pytest.raises(RuntimeError, match="Failed to create Tailscale auth key"):
        token_manager.create_tailscale_auth_key("device2", "client")


# === Tests for create_token ===

@patch("rfd.connections_manager.token_manager.create_tailscale_auth_key")
@patch("rfd.connections_manager.token_manager.hash_token")
def test_create_token_success(mock_hash_token, mock_create_key):
    # Mock dependencies
    mock_create_key.return_value = ("tskey-xyz", 1)
    mock_hash_token.return_value = "HASHED123"

    # Given base inputs
    base = "mission_group_abcdef123456"
    tag = "gcs"

    # When
    token, token_hash, expires, hostname = token_manager.create_token(base, tag)

    # Then
    assert token == "tskey-xyz"
    assert token_hash == "HASHED123"
    assert isinstance(expires, datetime)
    assert hostname == "gcs-ef123456"
