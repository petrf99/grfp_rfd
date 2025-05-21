import logging
import sys
import os
from pathlib import Path
import time

def init_logger(name: str = "App") -> logging.Logger:

    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    to_file = os.getenv("LOG_TO_FILE", None)
    to_stdout = os.getenv("LOG_TO_STDOUT", "True").lower() in ("1", "true", "yes")

    level = getattr(logging, level_str, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []  # Очистим, чтобы не дублировалось

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.Formatter.converter = time.gmtime

    handlers = []

    if to_stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        handlers.append(sh)

    if to_file:
        log_path = Path(to_file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path)
        fh.setFormatter(formatter)
        handlers.append(fh)

    # Добавляем все хендлеры к нашему логгеру
    for handler in handlers:
        logger.addHandler(handler)

    # 🔁 Настроим werkzeug логгер, чтобы он логировал в те же хендлеры
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(level)
    werkzeug_logger.handlers = handlers
    werkzeug_logger.propagate = False  # чтобы не дублировалось

    return logger
