"""
Logging Setup
"""
import logging
import os
from src.core.config import settings


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.LOG_FILE, encoding="utf-8"),
        ],
    )
    # Silence noisy libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
