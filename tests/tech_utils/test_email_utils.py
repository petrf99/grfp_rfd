# tests/tech_utils/test_email_utils.py

import pytest
from unittest.mock import patch, MagicMock
from tech_utils.email_utils import send_email

@patch("smtplib.SMTP")
def test_send_email_success(mock_smtp):
    # Подготовка
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    subject = "Test Subject"
    body = "Test Body"
    to = "test@example.com"

    # Действие
    send_email(subject, body, to)

    # Проверки
    mock_smtp.assert_called_once()
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.send_message.assert_called_once()
