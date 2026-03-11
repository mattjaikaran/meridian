#!/usr/bin/env python3
"""Tests for Meridian database reliability layer."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from scripts.db import (
    DatabaseBusyError,
    backup_database,
    open_project,
    retry_on_busy,
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
