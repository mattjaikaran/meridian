#!/usr/bin/env python3
"""Tests for database safety features: backup before migrations and BUSY retry."""

import sqlite3
import time
from unittest.mock import patch

import pytest

from scripts.db import (
    DatabaseBusyError,
    backup_database,
    init_schema,
    retry_on_busy,
)


# -- backup_database tests ----------------------------------------------------


class TestBackupDatabaseSafety:
    def test_creates_backup_file(self, tmp_path):
        """backup_database creates a timestamped backup in the backups/ directory."""
        db_path = tmp_path / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        conn.close()

        backup_path = backup_database(db_path)
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.parent.name == "backups"
        assert backup_path.name.startswith("state-")
        assert backup_path.suffix == ".db"

        # Verify backup has the data
        bconn = sqlite3.connect(str(backup_path))
        row = bconn.execute("SELECT id FROM t").fetchone()
        assert row[0] == 42
        bconn.close()

    def test_returns_none_for_nonexistent_db(self, tmp_path):
        """backup_database returns None when the source DB does not exist."""
        db_path = tmp_path / "nonexistent.db"
        result = backup_database(db_path)
        assert result is None

    def test_keeps_only_max_backups(self, tmp_path):
        """backup_database prunes old backups to keep only max_backups most recent."""
        db_path = tmp_path / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        # Create 8 backups with max_backups=5
        for _ in range(8):
            backup_database(db_path, max_backups=5)

        backup_dir = db_path.parent / "backups"
        backups = list(backup_dir.glob("state-*.db"))
        assert len(backups) <= 5

    def test_backup_called_before_migration(self, tmp_path):
        """init_schema calls backup_database before running migrations on real DBs."""
        db_path = tmp_path / "state.db"
        # Create a v1 DB
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        # Minimal schema for v1
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        # Create tables that migrations will ALTER
        conn.execute(
            "CREATE TABLE IF NOT EXISTS phase "
            "(id INTEGER PRIMARY KEY, milestone_id TEXT, sequence INTEGER, "
            "name TEXT, status TEXT DEFAULT 'planned')"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS plan "
            "(id INTEGER PRIMARY KEY, phase_id INTEGER, sequence INTEGER, "
            "name TEXT, description TEXT, status TEXT DEFAULT 'pending')"
        )
        conn.commit()
        conn.close()

        with patch("scripts.db.backup_database", wraps=backup_database) as mock_backup:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            init_schema(conn, db_path=db_path)
            conn.close()

            # Should have been called at least once (before v1->v2 migration)
            assert mock_backup.call_count >= 1


# -- retry_on_busy tests ------------------------------------------------------


class TestRetryOnBusySafety:
    def test_retries_on_database_locked(self):
        """retry_on_busy retries when sqlite3.OperationalError 'database is locked' occurs."""
        call_count = 0

        @retry_on_busy(max_retries=3, base_delay=0.01)
        def flaky_write():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "success"

        result = flaky_write()
        assert result == "success"
        assert call_count == 3

    def test_gives_up_after_max_retries(self):
        """retry_on_busy raises DatabaseBusyError after exhausting retries."""
        call_count = 0

        @retry_on_busy(max_retries=3, base_delay=0.01)
        def always_locked():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(DatabaseBusyError) as exc_info:
            always_locked()

        # max_retries=3 means initial attempt + 3 retries = 4 total calls
        assert call_count == 4
        assert exc_info.value.retries == 3

    def test_exponential_backoff(self):
        """retry_on_busy uses exponential backoff between retries."""
        call_times = []

        @retry_on_busy(max_retries=3, base_delay=0.05)
        def always_locked():
            call_times.append(time.monotonic())
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(DatabaseBusyError):
            always_locked()

        # Check that delays increase (with some tolerance for jitter)
        assert len(call_times) == 4  # initial + 3 retries
        delays = [call_times[i + 1] - call_times[i] for i in range(len(call_times) - 1)]
        # Each delay should be roughly 2x the previous (base_delay * 2^attempt +/- jitter)
        # delay[0] ~= 0.05, delay[1] ~= 0.1, delay[2] ~= 0.2
        assert delays[1] > delays[0] * 1.2  # second delay bigger than first
        assert delays[2] > delays[1] * 1.2  # third delay bigger than second

    def test_does_not_retry_other_errors(self):
        """retry_on_busy does NOT catch non-locked OperationalErrors."""

        @retry_on_busy(max_retries=3, base_delay=0.01)
        def bad_sql():
            raise sqlite3.OperationalError("no such table: foo")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            bad_sql()

    def test_passes_through_on_success(self):
        """retry_on_busy passes through return value when no error occurs."""

        @retry_on_busy(max_retries=3, base_delay=0.01)
        def always_works():
            return {"id": 1, "name": "test"}

        result = always_works()
        assert result == {"id": 1, "name": "test"}
