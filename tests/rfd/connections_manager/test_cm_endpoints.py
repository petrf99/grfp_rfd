import pytest
from unittest.mock import patch, MagicMock, mock_open
from flask import Flask
from rfd.connections_manager.endpoints import (
    register_gcs,
    get_vpn_connection,
    delete_vpn_connection,
    start_session,
    close_session
)

@pytest.fixture
def app():
    app = Flask(__name__)
    app.add_url_rule('/register-gcs', view_func=register_gcs, methods=['POST'])
    app.add_url_rule('/get-vpn-connection', view_func=get_vpn_connection, methods=['POST'])
    app.add_url_rule('/delete-vpn-connection', view_func=delete_vpn_connection, methods=['POST'])
    app.add_url_rule('/start-session', view_func=start_session, methods=['POST'])
    app.add_url_rule('/close-session', view_func=close_session, methods=['POST'])
    return app

@pytest.fixture
def client(app):
    return app.test_client()

# === Test register_gcs ===

@patch("builtins.open")
def test_register_gcs(mock_open, client):
    mock_open.side_effect = [
        MagicMock(read=MagicMock(return_value="")),  # read tokens
        MagicMock(write=MagicMock())  # write token
    ]
    response = client.post("/register-gcs")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert "gcs_proof_token" in response.json

# === Test get_vpn_connection_gcs ===

@patch("rfd.connections_manager.endpoints.get_conn")
@patch("rfd.connections_manager.endpoints.create_token")
@patch("rfd.connections_manager.endpoints.serialization.load_pem_public_key")
@patch("builtins.open")
def test_get_vpn_connection_gcs_success(mock_open, mock_load_key, mock_create_token, mock_get_conn, client):
    mock_open.return_value.__enter__.return_value.read.return_value = "validtoken"
    mock_create_token.return_value = ("token", "hash", "2025-01-01T00:00:00Z", "hostname")
    mock_key = MagicMock()
    mock_key.encrypt.return_value = b"encrypted"
    mock_load_key.return_value = mock_key

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = True
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/get-vpn-connection", json={
        "tag": "gcs",
        "rsa_pub_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
        "gcs_proof_token": "validtoken",
        "mission_group": "group123"
    })
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_get_vpn_connection_missing_tag(client):
    response = client.post("/get-vpn-connection", json={})
    assert response.status_code == 400
    assert response.json["status"] == "error"


def test_get_vpn_connection_missing_pubkey(client):
    response = client.post("/get-vpn-connection", json={"tag": "gcs"})
    assert response.status_code == 400
    assert "Missing public key" in response.json["reason"]


@patch("rfd.connections_manager.endpoints.get_conn")
@patch("rfd.connections_manager.endpoints.open", new_callable=mock_open, read_data="wrontpublickey")
def test_get_vpn_connection_invalid_public_key(mock_open_file, mock_get_conn, client):
    payload = {
        "tag": "gcs",
        "rsa_pub_key": """-----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArJkg3qvn+3VJHzzLQwA/
    7Ltn5+K9v5ogU2kkz3JrIXZmcI4OZslZ+ZK0rmGJNRcI4P0rB7YOiQKZLujZ+aTL
    -----END PUBLIC KEY-----""", # Invalid public key
        "gcs_proof_token": "validtoken",  
        "mission_group": "group1"
    }

    response = client.post("/get-vpn-connection", json=payload)
    assert response.status_code == 400
    assert "Invalid public key format" in response.json["reason"]

@patch("rfd.connections_manager.endpoints.get_conn")
@patch("rfd.connections_manager.endpoints.serialization.load_pem_public_key")
@patch("rfd.connections_manager.endpoints.open", new_callable=mock_open, read_data="wrontgcsprooftoken")
def test_get_vpn_connection_invalid_gcs_proof_token(mock_open_file, mock_load_key, mock_get_conn, client):
    payload = {
        "tag": "gcs",
        "rsa_pub_key": """-----BEGIN PUBLIC KEY-----\n....\n-----END PUBLIC KEY-----""",
        "gcs_proof_token": "invalid",  
        "mission_group": "group1"
    }

    response = client.post("/get-vpn-connection", json=payload)
    assert response.status_code == 400
    assert "Missing or invalid" in response.json["reason"]

# === Test delete_vpn_conection ===

@patch("rfd.connections_manager.endpoints.get_conn")
@patch("rfd.connections_manager.endpoints.update_versioned")
@patch("rfd.connections_manager.endpoints.remove_from_tailnet")
def test_delete_vpn_connection_success(mock_remove, mock_update, mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = True
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/delete-vpn-connection", json={
        "hostname": "somehost",
        "token_hash": "sometoken"
    })
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_delete_vpn_connection_missing_params(client):
    response = client.post("/delete-vpn-connection", json={})
    assert response.status_code == 400
    assert response.json["status"] == "error"


@patch("rfd.connections_manager.endpoints.get_conn")
def test_delete_vpn_connection_not_found(mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    payload = {"hostname": "fakehost", "token_hash": "fakehash"}
    response = client.post("/delete-vpn-connection", json=payload)
    assert response.status_code == 403

# === Test start_session ===

@patch("rfd.connections_manager.endpoints.get_conn")
@patch("builtins.open")
def test_start_session_success(mock_open, mock_get_conn, client):
    mock_open.return_value.__enter__.return_value.read.return_value = "validtoken"

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = True
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/start-session", json={
        "gcs_proof_token": "validtoken",
        "session_id": "sess123",
        "mission_id": "miss456"
    })
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_start_session_missing_fields(client):
    response = client.post("/start-session", json={})
    assert response.status_code == 400


@patch("rfd.connections_manager.endpoints.open", new_callable=mock_open, read_data="")
def test_start_session_invalid_token(mock_open_file, client):
    payload = {"gcs_proof_token": "abc", "session_id": "s1", "mission_id": "m1"}
    response = client.post("/start-session", json=payload)
    assert response.status_code == 400
    assert "Gcs proof token not found" in response.json["reason"]

# === Test close_session ===

@patch("rfd.connections_manager.endpoints.get_conn")
@patch("rfd.connections_manager.endpoints.update_versioned")
@patch("builtins.open")
def test_close_session_success(mock_open, mock_update, mock_get_conn, client):
    mock_open.return_value.__enter__.return_value.read.return_value = "validtoken"

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = True
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/close-session", json={
        "gcs_proof_token": "validtoken",
        "session_id": "sess789",
        "result": "finish"
    })
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_close_session_missing_fields(client):
    response = client.post("/close-session", json={})
    assert response.status_code == 400


@patch("rfd.connections_manager.endpoints.open", new_callable=mock_open, read_data="")
def test_close_session_invalid_token(mock_open_file, client):
    payload = {"gcs_proof_token": "abc", "session_id": "s1", "result": "abort"}
    response = client.post("/close-session", json=payload)
    assert response.status_code == 400
    assert "Gcs proof token not found" in response.json["reason"]