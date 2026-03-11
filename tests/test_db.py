#!/usr/bin/env python3
"""Tests for Meridian database reliability layer."""

import logging
import sqlite3
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from scripts.db import (
    DatabaseBusyError,
    MeridianError,
    NeroUnreachableError,
    StateTransitionError,
    backup_database,
    open_project,
    retry_on_busy,
    retry_on_http_error,
    setup_logging,
)


# -- open_project tests -------------------------------------------------------


class TestOpenProject:
    def test_yields_connection(self, tmp_path):
        with open_project(tmp_path) as conn:
            assert isinstance(conn, sqlite3.Connection)
            assert conn.row_factory == sqlite3.Row

    def test_auto_commits(self, tmp_path):
        with open_project(tmp_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS test_tbl (id INTEGER PRIMARY KEY, val TEXT)"
            )
            conn.execute("INSERT INTO test_tbl (val) VALUES ('hello')")

        # Reopen and verify data persisted
        with open_project(tmp_path) as conn:
            row = conn.execute("SELECT val FROM test_tbl").fetchone()
            assert row["val"] == "hello"

    def test_rollback_on_exception(self, tmp_path):
        # First create table
        with open_project(tmp_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS test_tbl (id INTEGER PRIMARY KEY, val TEXT)"
            )

        # Now insert and raise -- should rollback
        with pytest.raises(RuntimeError):
            with open_project(tmp_path) as conn:
                conn.execute("INSERT INTO test_tbl (val) VALUES ('should_vanish')")
                raise RuntimeError("oops")

        # Verify data did NOT persist
        with open_project(tmp_path) as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM test_tbl").fetchone()
            assert row["cnt"] == 0

    def test_closes_connection(self, tmp_path):
        with open_project(tmp_path) as conn:
            pass
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    def test_memory_mode(self):
        with open_project(":memory:") as conn:
            assert isinstance(conn, sqlite3.Connection)
            # Schema should be initialized
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {r["name"] for r in tables}
            assert "project" in table_names


# -- busy_timeout tests -------------------------------------------------------


class TestBusyTimeout:
    def test_busy_timeout_pragma(self, tmp_path):
        with open_project(tmp_path) as conn:
            result = conn.execute("PRAGMA busy_timeout").fetchone()
            assert result[0] == 5000


# -- retry_on_busy tests ------------------------------------------------------


class TestRetryOnBusy:
    def test_succeeds_after_retry(self):
        call_count = 0

        @retry_on_busy(max_retries=3, base_delay=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 3

    def test_raises_database_busy_error(self):
        @retry_on_busy(max_retries=3, base_delay=0.01)
        def always_locked():
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(DatabaseBusyError) as exc_info:
            always_locked()
        assert exc_info.value.retries == 3
        assert exc_info.value.total_wait > 0

    def test_does_not_catch_other_errors(self):
        @retry_on_busy(max_retries=3, base_delay=0.01)
        def bad_sql():
            raise sqlite3.OperationalError("no such table: foo")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            bad_sql()


# -- backup tests --------------------------------------------------------------


class TestBackup:
    def test_creates_backup_file(self, tmp_path):
        # Create a DB first
        db_path = tmp_path / ".meridian" / "state.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        backup_path = backup_database(db_path)
        assert backup_path.exists()
        assert "state-" in backup_path.name
        assert backup_path.suffix == ".db"
        assert backup_path.parent.name == "backups"

    def test_prune_backups(self, tmp_path):
        db_path = tmp_path / ".meridian" / "state.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        # Create 5 backups with max_backups=3
        for _ in range(5):
            backup_database(db_path, max_backups=3)

        backup_dir = db_path.parent / "backups"
        backups = list(backup_dir.glob("state-*.db"))
        assert len(backups) <= 3


# -- error hierarchy tests ----------------------------------------------------


class TestErrorHierarchy:
    def test_meridian_error_is_base(self):
        err = MeridianError("test")
        assert isinstance(err, Exception)
        assert isinstance(err, MeridianError)

    def test_database_busy_inherits_meridian(self):
        err = DatabaseBusyError(retries=3, total_wait=1.5)
        assert isinstance(err, MeridianError)
        assert isinstance(err, Exception)

    def test_state_transition_error(self):
        err = StateTransitionError("invalid transition")
        assert isinstance(err, MeridianError)
        assert str(err) == "invalid transition"

    def test_nero_unreachable_error(self):
        err = NeroUnreachableError("connection refused")
        assert isinstance(err, MeridianError)
        assert str(err) == "connection refused"

    def test_catch_all_via_base(self):
        """Catching MeridianError catches all subclasses."""
        errors = [
            DatabaseBusyError(retries=1, total_wait=0.5),
            StateTransitionError("bad"),
            NeroUnreachableError("down"),
        ]
        for err in errors:
            with pytest.raises(MeridianError):
                raise err


# -- logging tests ------------------------------------------------------------


class TestLogging:
    def test_setup_logging_configures_stderr(self):
        import scripts.db as db_module

        db_module._logging_configured = False
        setup_logging()
        root = logging.getLogger()
        # Should have at least one StreamHandler pointing to stderr
        stderr_handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.StreamHandler)
            and hasattr(h, "stream")
            and h.stream.name == "<stderr>"
        ]
        assert len(stderr_handlers) >= 1
        # Check format
        handler = stderr_handlers[-1]
        assert handler.formatter._fmt == "%(name)s: %(message)s"

    def test_setup_logging_default_warning(self):
        import scripts.db as db_module

        db_module._logging_configured = False
        with patch.dict("os.environ", {}, clear=True):
            # Remove MERIDIAN_LOG_LEVEL if present
            import os

            os.environ.pop("MERIDIAN_LOG_LEVEL", None)
            setup_logging()
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_setup_logging_env_override(self):
        import scripts.db as db_module

        db_module._logging_configured = False
        with patch.dict("os.environ", {"MERIDIAN_LOG_LEVEL": "DEBUG"}):
            setup_logging()
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_open_project_calls_setup_logging(self):
        import scripts.db as db_module

        db_module._logging_configured = False
        with open_project(":memory:") as conn:
            pass
        assert db_module._logging_configured is True


# -- retry_on_http_error tests ------------------------------------------------


class TestRetryOnHttpError:
    def test_succeeds_without_error(self):
        @retry_on_http_error(max_retries=3, base_delay=0.01)
        def ok():
            return "success"

        assert ok() == "success"

    def test_retries_on_5xx(self):
        call_count = 0

        @retry_on_http_error(max_retries=3, base_delay=0.01)
        def flaky_server():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.HTTPError(
                    "http://example.com", 503, "Service Unavailable", {}, None
                )
            return "ok"

        assert flaky_server() == "ok"
        assert call_count == 2

    def test_no_retry_on_4xx(self):
        call_count = 0

        @retry_on_http_error(max_retries=3, base_delay=0.01)
        def client_error():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "http://example.com", 404, "Not Found", {}, None
            )

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            client_error()
        assert exc_info.value.code == 404
        assert call_count == 1  # No retries

    def test_retries_on_url_error(self):
        call_count = 0

        @retry_on_http_error(max_retries=3, base_delay=0.01)
        def connection_refused():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.URLError("Connection refused")
            return "ok"

        assert connection_refused() == "ok"
        assert call_count == 2

    def test_retries_on_timeout(self):
        call_count = 0

        @retry_on_http_error(max_retries=3, base_delay=0.01)
        def timeout_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timed out")
            return "ok"

        assert timeout_func() == "ok"
        assert call_count == 2

    def test_raises_nero_unreachable_after_exhaustion(self):
        @retry_on_http_error(max_retries=2, base_delay=0.01)
        def always_fails():
            raise urllib.error.URLError("Connection refused")

        with pytest.raises(NeroUnreachableError, match="Nero unreachable after 2 retries"):
            always_fails()

    @patch("scripts.db.time.sleep")
    def test_backoff_delays(self, mock_sleep):
        call_count = 0

        @retry_on_http_error(max_retries=3, base_delay=1.0)
        def always_503():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "http://example.com", 503, "Service Unavailable", {}, None
            )

        with pytest.raises(NeroUnreachableError):
            always_503()

        # Should have called sleep 3 times with exponential backoff
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(delays) == 3
        assert delays[0] == 1.0   # base_delay * 2^0
        assert delays[1] == 2.0   # base_delay * 2^1
        assert delays[2] == 4.0   # base_delay * 2^2
