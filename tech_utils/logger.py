import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from pathlib import Path
import time

def init_logger(name: str = "App", component: str = None) -> logging.Logger:
    """
    Initialize and configure a logger.

    Supports logging to stdout and/or to a file, with log level set via environment variables:
    - LOG_LEVEL      (e.g., "DEBUG", "INFO", "WARNING")
    - LOG_TO_STDOUT  ("true"/"false", default: true)
    - LOG_TO_FILE    (file path, optional)
    """
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    to_file_base = os.getenv("LOG_TO_FILE_BASE", None)
    to_stdout = os.getenv("LOG_TO_STDOUT", "True").lower() in ("1", "true", "yes")

    level = getattr(logging, level_str, logging.INFO)

    if component:
        logger = logging.getLogger(name + f"_{component}")
    else:
        logger = logging.getLogger(name)
    logger.propagate = False  # Prevent logs from being propagated to the root logger
    logger.setLevel(level)

    # Remove any existing handlers (important for interactive environments)
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Use UTC time in logs
    logging.Formatter.converter = time.gmtime

    handlers = []

    if to_stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        handlers.append(sh)

    if to_file_base:
        filename = to_file_base
        if component:
            filename += f"_{component}"
        filename += ".log"
        log_path = Path(filename).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5              # Keep 5 backups
        )
        fh.setFormatter(formatter)
        handlers.append(fh)

    for handler in handlers:
        logger.addHandler(handler)

    # === Настройка отдельного логгера для werkzeug ===
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(level)

    if to_file_base:
        werkzeug_log_path = Path(to_file_base + "_werkzeug.log").resolve()
    else:
        werkzeug_log_path = Path("werkzeug.log").resolve()
    werkzeug_log_path.parent.mkdir(parents=True, exist_ok=True)

    werkzeug_handler = RotatingFileHandler(
        werkzeug_log_path, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    werkzeug_handler.setFormatter(formatter)

    # Удаляем stdout, если был, и вешаем только file-хендлер
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(werkzeug_handler)
    werkzeug_logger.propagate = False


    return logger
