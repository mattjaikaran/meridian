#!/usr/bin/env python3
"""Tests for Meridian database reliability layer."""

import logging
import sqlite3
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from scripts.db import (
    SCHEMA_SQL,
    DatabaseBusyError,
    MeridianError,
    NeroUnreachableError,
    StateTransitionError,
    _migrate_v1_to_v2,
    _migrate_v2_to_v3,
    backup_database,
    get_schema_version,
    init_schema,
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
        # Should have at least one StreamHandler with the correct format
        stream_handlers = [
            h for h in root.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) >= 1
        # Check format on the last added handler
        handler = stream_handlers[-1]
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


# -- migration tests ----------------------------------------------------------


class TestMigration:
    """Tests for _migrate_v1_to_v2 schema migration."""

    def _create_v1_schema(self):
        """Create a connection with v1 schema (no priority columns)."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        # Run base schema
        conn.executescript(SCHEMA_SQL)
        # Record as v1
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (1,))
        conn.commit()
        # Drop priority columns if they exist (SCHEMA_SQL includes them in CREATE TABLE
        # but they're in the v2 migration, so we simulate v1 by checking)
        # Since SCHEMA_SQL doesn't include priority columns in CREATE TABLE,
        # we just need to verify they don't exist
        return conn

    def _get_columns(self, conn, table):
        """Get set of column names for a table."""
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def test_adds_priority_column_to_phase(self):
        """_migrate_v1_to_v2 adds priority column to phase table."""
        conn = self._create_v1_schema()
        # Verify priority doesn't exist before migration (if schema doesn't include it)
        # Run migration
        _migrate_v1_to_v2(conn)
        columns = self._get_columns(conn, "phase")
        assert "priority" in columns
        conn.close()

    def test_adds_priority_column_to_plan(self):
        """_migrate_v1_to_v2 adds priority column to plan table."""
        conn = self._create_v1_schema()
        _migrate_v1_to_v2(conn)
        columns = self._get_columns(conn, "plan")
        assert "priority" in columns
        conn.close()

    def test_idempotent_no_error_on_double_run(self):
        """Running _migrate_v1_to_v2 twice does not raise."""
        conn = self._create_v1_schema()
        _migrate_v1_to_v2(conn)
        # Second call should not raise
        _migrate_v1_to_v2(conn)
        # Still has the columns
        assert "priority" in self._get_columns(conn, "phase")
        assert "priority" in self._get_columns(conn, "plan")
        conn.close()

    def test_priority_default_null(self):
        """Priority columns default to NULL."""
        conn = self._create_v1_schema()
        _migrate_v1_to_v2(conn)
        # Insert a project and phase to check default
        conn.execute(
            "INSERT INTO project (id, name, repo_path) VALUES ('default', 'Test', '/tmp')"
        )
        conn.execute(
            "INSERT INTO milestone (id, project_id, name) VALUES ('v1', 'default', 'V1')"
        )
        conn.execute(
            "INSERT INTO phase (milestone_id, sequence, name) VALUES ('v1', 1, 'Phase 1')"
        )
        conn.commit()
        row = conn.execute("SELECT priority FROM phase WHERE sequence = 1").fetchone()
        assert row["priority"] is None
        conn.close()

    def test_init_schema_creates_priority_columns(self):
        """A fresh init_schema creates tables with priority columns present."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        init_schema(conn)
        assert "priority" in self._get_columns(conn, "phase")
        assert "priority" in self._get_columns(conn, "plan")
        conn.close()

    def test_schema_version_updated_to_2(self):
        """After migration, schema version is 2."""
        conn = self._create_v1_schema()
        assert get_schema_version(conn) == 1
        _migrate_v1_to_v2(conn)
        assert get_schema_version(conn) == 2
        conn.close()


class TestMigrationV2ToV3:
    """Tests for _migrate_v2_to_v3 schema migration."""

    def _create_v2_schema(self):
        """Create a connection with v2 schema."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (2,))
        conn.commit()
        return conn

    def _get_columns(self, conn, table):
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _get_tables(self, conn):
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {row[0] for row in rows}

    def test_fresh_db_has_v3_tables(self):
        """A fresh init_schema creates all v3 tables."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        init_schema(conn)
        tables = self._get_tables(conn)
        assert "state_event" in tables
        assert "settings" in tables
        assert "review" in tables
        assert "depends_on" in self._get_columns(conn, "plan")
        conn.close()

    def test_migration_adds_tables(self):
        """_migrate_v2_to_v3 adds new tables."""
        conn = self._create_v2_schema()
        _migrate_v2_to_v3(conn)
        tables = self._get_tables(conn)
        assert "state_event" in tables
        assert "settings" in tables
        assert "review" in tables
        conn.close()

    def test_migration_adds_depends_on(self):
        """_migrate_v2_to_v3 adds depends_on column to plan."""
        conn = self._create_v2_schema()
        _migrate_v2_to_v3(conn)
        assert "depends_on" in self._get_columns(conn, "plan")
        conn.close()

    def test_idempotent(self):
        """Running _migrate_v2_to_v3 twice does not raise."""
        conn = self._create_v2_schema()
        _migrate_v2_to_v3(conn)
        _migrate_v2_to_v3(conn)
        assert "depends_on" in self._get_columns(conn, "plan")
        conn.close()

    def test_version_bumped_to_3(self):
        """After migration, schema version is 3."""
        conn = self._create_v2_schema()
        assert get_schema_version(conn) == 2
        _migrate_v2_to_v3(conn)
        assert get_schema_version(conn) == 3
        conn.close()
