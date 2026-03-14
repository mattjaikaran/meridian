"""Tests for Meridian structured logging configuration."""

import logging
from pathlib import Path

import pytest

from scripts.logging_config import get_logger


@pytest.fixture(autouse=True)
def _clean_loggers():
    """Remove test loggers between tests to avoid handler accumulation."""
    yield
    # Clean up any loggers we created
    manager = logging.Logger.manager
    to_remove = [name for name in manager.loggerDict if name.startswith("test_meridian")]
    for name in to_remove:
        logger = logging.getLogger(name)
        logger.handlers.clear()


def test_get_logger_returns_logger() -> None:
    """get_logger returns a logging.Logger instance."""
    logger = get_logger("test_meridian.basic")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_meridian.basic"


def test_get_logger_returns_same_instance() -> None:
    """Calling get_logger twice with the same name returns the same logger."""
    logger1 = get_logger("test_meridian.same")
    logger2 = get_logger("test_meridian.same")
    assert logger1 is logger2


def test_file_handler_added_when_meridian_dir_exists(tmp_path: Path) -> None:
    """File handler is added when .meridian/ directory exists."""
    meridian_dir = tmp_path / ".meridian"
    meridian_dir.mkdir()

    logger = get_logger("test_meridian.file_handler", project_dir=tmp_path)

    handler_types = [type(h) for h in logger.handlers]
    assert logging.StreamHandler in handler_types
    from logging.handlers import RotatingFileHandler

    assert RotatingFileHandler in handler_types

    # Verify log file path
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1
    assert Path(file_handlers[0].baseFilename) == meridian_dir / "meridian.log"


def test_only_stream_handler_when_no_project_dir() -> None:
    """Only stderr stream handler when no project_dir provided."""
    logger = get_logger("test_meridian.stream_only")

    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_only_stream_handler_when_meridian_dir_missing(tmp_path: Path) -> None:
    """Only stderr stream handler when .meridian/ doesn't exist."""
    logger = get_logger("test_meridian.no_dir", project_dir=tmp_path)

    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_logger_level_is_debug() -> None:
    """Logger level is set to DEBUG to allow all messages through."""
    logger = get_logger("test_meridian.level")
    assert logger.level == logging.DEBUG
