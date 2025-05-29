import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from rfd.missions_manager.endpoints import (
    mission_request, mission_group_request, change_mission_status, get_missions_list
)

# === Test setup ===
@pytest.fixture
def app():
    app = Flask(__name__)
    app.add_url_rule('/mission-request', view_func=mission_request, methods=['POST'])
    app.add_url_rule('/mission-group-request', view_func=mission_group_request, methods=['POST'])
    app.add_url_rule('/change-mission-status', view_func=change_mission_status, methods=['POST'])
    app.add_url_rule('/get-missions-list', view_func=get_missions_list, methods=['POST'])
    return app

@pytest.fixture
def client(app):
    return app.test_client()


# === /mission-request ===
def test_mission_request_returns_400_when_missing_fields(client):
    response = client.post("/mission-request", json={})
    assert response.status_code == 400
    assert response.json["status"] == "error"


@patch("rfd.missions_manager.endpoints.get_conn")
@patch("rfd.missions_manager.endpoints.send_email")
def test_mission_request_with_mission_group(mock_send_email, mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    payload = {
        "user_id": "user123",
        "location": "Area 51",
        "time_window": "Tomorrow",
        "drone_type": "Quad",
        "mission_group": "groupA"
    }

    response = client.post("/mission-request", json=payload)
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    mock_send_email.assert_called_once()


@patch("rfd.missions_manager.endpoints.get_conn")
@patch("rfd.missions_manager.endpoints.send_email")
def test_mission_request_without_mission_group(mock_send_email, mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    payload = {
        "user_id": "user123",
        "location": "Area 51",
        "time_window": "Tomorrow",
        "drone_type": "Quad"
    }

    response = client.post("/mission-request", json=payload)
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    mock_send_email.assert_called_once()


# === /mission-group-request ===
@patch("rfd.missions_manager.endpoints.get_conn")
def test_mission_group_request_creates_group_successfully(mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/mission-group-request", json={"mission_group": "test_group"})
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_mission_group_request_returns_400_when_missing_group(client):
    response = client.post("/mission-group-request", json={})
    assert response.status_code == 400
    assert response.json["status"] == "error"


# === /change-mission-status ===
@patch("rfd.missions_manager.endpoints.get_conn")
@patch("rfd.missions_manager.endpoints.update_versioned")
@patch("rfd.missions_manager.endpoints.send_email")
def test_change_mission_status_successful(mock_send_email, mock_update_versioned, mock_get_conn, client):
    mock_get_conn.return_value = MagicMock()

    response = client.post("/change-mission-status", json={
        "mission_id": "abc-123",
        "new_status": "in progress"
    })
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    mock_update_versioned.assert_called_once()
    mock_send_email.assert_called_once()


@pytest.mark.parametrize("payload", [
    {},
    {"mission_id": "abc-123"},
    {"new_status": "in progress"},
])
def test_change_mission_status_returns_400_on_missing_fields(client, payload):
    response = client.post("/change-mission-status", json=payload)
    assert response.status_code == 400
    assert response.json["status"] == "error"


# === /get-missions-list ===
@patch("rfd.missions_manager.endpoints.get_conn")
def test_get_missions_list_with_filters(mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"mission_id": "abc", "status": "new"}]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/get-missions-list", json={"user_id": "test_user"})
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert isinstance(response.json["data"], list)


@patch("rfd.missions_manager.endpoints.get_conn")
def test_get_missions_list_without_filters(mock_get_conn, client):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"mission_id": "abc", "status": "new"}]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    response = client.post("/get-missions-list", json={})
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert isinstance(response.json["data"], list)
