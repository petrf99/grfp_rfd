import pytest
from unittest.mock import patch, MagicMock
from rfd.missions_manager.jobs import alert_pending_tasks  # путь поправь под свой

# === Test when there are pending tasks ===
@patch("rfd.missions_manager.jobs.send_email")
@patch("rfd.missions_manager.jobs.get_conn")
def test_alert_pending_tasks_with_new_tasks(mock_get_conn, mock_send_email):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("task1", "Zone A", "12:00-13:00", "Quad", "2024-05-01 12:00:00"),
        ("task2", "Zone B", "14:00-15:00", "Hex", "2024-05-01 13:00:00"),
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    alert_pending_tasks()

    mock_send_email.assert_called_once()
    args = mock_send_email.call_args[0]
    assert "[GRFP] Hourly Alert: Pending Missions" in args[0]
    assert "Pending Missions:" in args[1]
    assert "task1" in args[1]
    assert "Zone A" in args[1]


# === Test when there are NO pending tasks ===
@patch("rfd.missions_manager.jobs.send_email")
@patch("rfd.missions_manager.jobs.get_conn")
def test_alert_pending_tasks_without_tasks(mock_get_conn, mock_send_email):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    alert_pending_tasks()

    mock_send_email.assert_not_called()


# === Test exception handling ===
@patch("rfd.missions_manager.jobs.get_conn", side_effect=Exception("DB failure"))
@patch("rfd.missions_manager.jobs.send_email")
def test_alert_pending_tasks_db_error(mock_send_email, mock_get_conn):
    # just ensure no exception is raised and nothing is sent
    alert_pending_tasks()
    mock_send_email.assert_not_called()
