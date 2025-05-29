import os
import logging
from tech_utils.logger import init_logger

def test_logger_stdout(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_TO_STDOUT", "true")
    monkeypatch.delenv("LOG_TO_FILE", raising=False)

    logger = init_logger("TestLogger")

    assert logger.level == logging.DEBUG
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
