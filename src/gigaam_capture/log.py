from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "gigaam_capture"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

__all__ = ["configure_logging", "get_logger", "LOG_FORMAT", "LOGGER_NAME"]


def get_logger(name: str) -> logging.Logger:
    """Return an application logger namespaced under the app logger."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logging(log_path: Path, level: int = logging.INFO) -> logging.Logger:
    """Attach a rotating file handler and a stream handler to the app logger.

    The file handler captures everything from ``level`` up, while the stream
    handler only surfaces warnings and errors so command-line tools keep a clean
    stdout/stderr. The call is idempotent: repeated invocations with the same
    path do not add duplicate handlers.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    file_handler = _file_handler(log_path)
    if file_handler is not None:
        logger.addHandler(file_handler)

    if not any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
        for handler in logger.handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(stream_handler)

    return logger


def _file_handler(log_path: Path) -> RotatingFileHandler | None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            if Path(handler.baseFilename) == log_path:
                return None

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler
