import logging
import sys
import os
from pathlib import Path
import time

def init_logger(name: str = "App") -> logging.Logger:
    """
    Initialize and configure a logger.

    Supports logging to stdout and/or to a file, with log level set via environment variables:
    - LOG_LEVEL      (e.g., "DEBUG", "INFO", "WARNING")
    - LOG_TO_STDOUT  ("true"/"false", default: true)
    - LOG_TO_FILE    (file path, optional)
    """
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    to_file = os.getenv("LOG_TO_FILE", None)
    to_stdout = os.getenv("LOG_TO_STDOUT", "True").lower() in ("1", "true", "yes")

    level = getattr(logging, level_str, logging.INFO)

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

    if to_file:
        log_path = Path(to_file).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path)
        fh.setFormatter(formatter)
        handlers.append(fh)

    for handler in handlers:
        logger.addHandler(handler)

    # Disable werkzeug logging to avoid polluting logs with HTTP noise
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(level)
    werkzeug_logger.handlers = []        # Intentionally left empty — no stdout or file
    werkzeug_logger.propagate = False    # Don't forward to root logger


    return logger
