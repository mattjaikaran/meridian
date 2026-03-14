"""Meridian structured logging configuration.

Provides a configured logger that writes to .meridian/meridian.log
with rotation. Falls back to stderr if .meridian/ doesn't exist.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str = "meridian", project_dir: Path | None = None) -> logging.Logger:
    """Get or create a Meridian logger.

    Args:
        name: Logger name (default: "meridian")
        project_dir: Project directory containing .meridian/.
                     If None or .meridian/ doesn't exist, logs to stderr only.

    Returns:
        Configured logger with file and/or stream handlers.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Always add stderr handler (INFO+)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Add file handler if .meridian/ exists
    if project_dir:
        log_dir = Path(project_dir) / ".meridian"
        if log_dir.is_dir():
            log_file = log_dir / "meridian.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
