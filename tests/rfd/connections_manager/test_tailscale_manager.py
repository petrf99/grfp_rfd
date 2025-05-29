import pytest
from unittest.mock import patch
from rfd.connections_manager import tailscale_manager

# === Test: OAuth token is fetched and cached ===
@patch("rfd.connections_manager.tailscale_manager.requests.post")
@patch("rfd.connections_manager.tailscale_manager.time")
def test_get_access_token_success(mock_time, mock_post):
    # Mock current time and response from Tailscale API
    mock_time.time.return_value = 1000
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "access_token": "mock_token",
        "expires_in": 3600
    }

    # First call fetches the token
    token = tailscale_manager.get_access_token()
    assert token == "mock_token"

# === Test: Successful retrieval of device list ===
@patch("rfd.connections_manager.tailscale_manager.get_access_token", return_value="token123")
@patch("rfd.connections_manager.tailscale_manager.requests.get")
def test_get_devices_success(mock_get, mock_token):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"devices": [{"hostname": "test-host", "id": "dev123"}]}

    devices = tailscale_manager.get_devices()
    assert isinstance(devices, list)
    assert devices[0]["hostname"] == "test-host"

# === Test: Handle bad 'devices' format ===
@patch("rfd.connections_manager.tailscale_manager.get_access_token", return_value="token123")
@patch("rfd.connections_manager.tailscale_manager.requests.get")
def test_get_devices_invalid_format(mock_get, mock_token):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"devices": "invalid-format"}

    assert tailscale_manager.get_devices() == []

# === Test: Fetch only auth keys from key list ===
@patch("rfd.connections_manager.tailscale_manager.requests.get")
def test_get_auth_keys_success(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "keys": [{"id": "auth1", "keyType": "auth"}, {"id": "key2", "keyType": "other"}]
    }

    keys = tailscale_manager.get_auth_keys()
    assert len(keys) == 1
    assert keys[0]["id"] == "auth1"

# === Test: Device deletion success ===
@patch("rfd.connections_manager.tailscale_manager.get_access_token", return_value="token123")
@patch("rfd.connections_manager.tailscale_manager.requests.delete")
def test_delete_device_success(mock_delete, mock_token):
    mock_delete.return_value.status_code = 200
    assert tailscale_manager.delete_device("device123")

# === Test: Device deletion failure ===
@patch("rfd.connections_manager.tailscale_manager.get_access_token", return_value="token123")
@patch("rfd.connections_manager.tailscale_manager.requests.delete")
def test_delete_device_failure(mock_delete, mock_token):
    mock_delete.return_value.status_code = 403
    mock_delete.return_value.text = "Forbidden"
    assert not tailscale_manager.delete_device("device123")

# === Test: Auth key deletion success ===
@patch("rfd.connections_manager.tailscale_manager.requests.delete")
def test_delete_auth_key_success(mock_delete):
    mock_delete.return_value.status_code = 200
    assert tailscale_manager.delete_auth_key("key123")

# === Test: Auth key not found ===
@patch("rfd.connections_manager.tailscale_manager.requests.delete")
def test_delete_auth_key_not_found(mock_delete):
    mock_delete.return_value.status_code = 404
    assert not tailscale_manager.delete_auth_key("key404")

# === Test: Auth key deletion error ===
@patch("rfd.connections_manager.tailscale_manager.requests.delete")
def test_delete_auth_key_error(mock_delete):
    mock_delete.return_value.status_code = 500
    mock_delete.return_value.text = "Server error"
    assert not tailscale_manager.delete_auth_key("key500")
