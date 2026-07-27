import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import AI_SERVER_DIR, settings


def configure_logging() -> Path:
    """Configure console and persistent rotating-file logs for every pipeline stage."""
    log_path = Path(settings.LOG_FILE)
    if not log_path.is_absolute():
        log_path = AI_SERVER_DIR / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s "
        "pid=%(process)d thread=%(threadName)s %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        handlers=[stream_handler, file_handler],
        force=True,
    )
    logging.captureWarnings(True)
    logging.getLogger(__name__).info("Logging initialized log_file=%s", log_path)
    return log_path
