import logging
import sys
import os
from pathlib import Path

def init_logger(name: str = "App") -> logging.Logger:
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    to_file = os.getenv("LOG_TO_FILE", None)
    handlers = [logging.StreamHandler(sys.stdout)]

    level = getattr(logging, level_str, logging.INFO)

    if to_file:
        log_path = Path(to_file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True) 
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers
    )

    return logging.getLogger(name)
