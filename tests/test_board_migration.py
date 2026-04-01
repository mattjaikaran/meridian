"""Tests for board column migration (axis_* → board_*)."""

from scripts.db import get_schema_version, open_project


class TestBoardMigration:
    """Migration v7 renames axis_* columns to board_*."""

    def test_fresh_db_has_board_columns(self):
        """New databases get board_* columns directly."""
        with open_project(":memory:") as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(project)").fetchall()}
            assert "board_project_id" in cols
            assert "axis_project_id" not in cols

            cols = {row[1] for row in conn.execute("PRAGMA table_info(phase)").fetchall()}
            assert "board_ticket_id" in cols
            assert "axis_ticket_id" not in cols

    def test_migration_reaches_v7(self):
        """Schema version is at least 7 after init."""
        with open_project(":memory:") as conn:
            version = get_schema_version(conn)
            assert version >= 7
