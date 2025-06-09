import pytest
from unittest.mock import patch, MagicMock

# === Tests for clean_session ===

@patch("rfd.connections_manager.cleaner.remove_from_tailnet")
@patch("rfd.connections_manager.cleaner.update_versioned")
@patch("rfd.connections_manager.cleaner.get_conn")
def test_clean_session_success(mock_get_conn, mock_update_versioned, mock_remove_from_tailnet):
    # Simulate a session in progress and with an active VPN hostname
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [("in progress",), ("hostname123",)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    from rfd.connections_manager.cleaner import clean_session
    clean_session("session123", "completed")

    # Ensure update_versioned is called twice and hostname is removed from Tailnet
    assert mock_update_versioned.call_count == 2
    mock_remove_from_tailnet.assert_called_once_with("hostname123")


@patch("rfd.connections_manager.cleaner.get_conn")
def test_clean_session_not_found(mock_get_conn):
    # Simulate a case where the session is not found in DB
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    from rfd.connections_manager.cleaner import clean_session
    clean_session("missing_session", "completed")  # Should do nothing, but not fail


@patch("rfd.connections_manager.cleaner.get_conn")
def test_clean_session_wrong_status(mock_get_conn):
    # Simulate a session with incorrect status (not 'in progress')
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [("completed",)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    from rfd.connections_manager.cleaner import clean_session
    clean_session("session_wrong_status", "aborted")  # Should skip update


# === Tests for cleaner ===

@patch("rfd.connections_manager.cleaner.update_versioned")
@patch("rfd.connections_manager.cleaner.clean_session")
@patch("rfd.connections_manager.cleaner.get_conn")
def test_cleaner_with_sessions(mock_get_conn, mock_clean_session, mock_update_versioned):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.side_effect = [
        [("session1",), ("session2",)],  # duplicate sessions
        [("session2",), ("session3",)]   # expired VPNs
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    from rfd.connections_manager.cleaner import cleaner
    cleaner()

    # Test call of clean_session
    assert mock_clean_session.call_count == 2
    cleaned_ids = {call.args[0] for call in mock_clean_session.call_args_list}
    assert cleaned_ids == {"session1", "session2"}

    # Test update_versioned for expired VPNs
    vpn_calls = [
        call.args for call in mock_update_versioned.call_args_list
        if call.args[0] == mock_conn and call.args[1] == 'vpn_connections'
    ]
    updated_ids = {kwargs[2]['parent_id'] for kwargs in vpn_calls}
    assert updated_ids == {"session2", "session3"}


@patch("rfd.connections_manager.cleaner.clean_session")
@patch("rfd.connections_manager.cleaner.get_conn")
def test_cleaner_no_sessions(mock_get_conn, mock_clean_session):
    # Simulate no sessions to clean
    mock_cursor = MagicMock()
    mock_cursor.fetchall.side_effect = [[], []]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value.__enter__.return_value = mock_conn

    from rfd.connections_manager.cleaner import cleaner
    cleaner()

    # No sessions should be processed
    mock_clean_session.assert_not_called()
