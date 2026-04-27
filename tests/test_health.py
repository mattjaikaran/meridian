"""Tests for the Meridian health check module."""

import pytest

from scripts.db import open_project
from scripts.health import (
    check_artifact_consistency,
    check_db_integrity,
    check_orphaned_rows,
    check_schema_version,
    check_stuck_phases,
    repair,
    run_health_check,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    transition_phase,
)


@pytest.fixture()
def conn():
    with open_project(":memory:") as c:
        create_project(c, "Test", "/tmp/test")
        yield c


@pytest.fixture()
def project_with_phase(conn, tmp_path):
    m = create_milestone(conn, "M1", "Milestone 1")
    ph = create_phase(conn, m["id"], "Build API")
    return conn, m, ph, tmp_path


# ── DB integrity ──────────────────────────────────────────────────────────────


class TestDbIntegrity:
    def test_clean_db_returns_no_findings(self, conn):
        assert check_db_integrity(conn) == []

    def test_foreign_key_check_no_violations(self, conn):
        findings = check_db_integrity(conn)
        fk_findings = [f for f in findings if f["check"] == "foreign_key_check"]
        assert fk_findings == []


class TestSchemaVersion:
    def test_current_version_passes(self, conn):
        assert check_schema_version(conn) == []

    def test_old_version_warns(self, conn):
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.commit()
        findings = check_schema_version(conn)
        assert len(findings) == 1
        assert findings[0]["level"] == "warning"
        assert "schema_version" in findings[0]["check"]


# ── Orphaned rows ─────────────────────────────────────────────────────────────


class TestOrphanedRows:
    def test_no_orphans_in_clean_db(self, conn):
        assert check_orphaned_rows(conn) == []

    def test_detects_orphaned_plan(self, conn):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Phase 1")
        # Temporarily disable FK checks to insert an orphaned row
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO plan (phase_id, sequence, name, description) VALUES (9999, 1, 'Ghost', 'x')"
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        findings = check_orphaned_rows(conn)
        assert any(f["check"] == "orphaned_rows" and "phase_id=9999" in f["message"] for f in findings)

    def test_detects_orphaned_phase(self, conn):
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO phase (milestone_id, sequence, name) VALUES ('nonexistent', 1, 'Ghost')"
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        findings = check_orphaned_rows(conn)
        assert any(
            f["check"] == "orphaned_rows" and "milestone_id=nonexistent" in f["message"]
            for f in findings
        )


# ── Artifact consistency ──────────────────────────────────────────────────────


class TestArtifactConsistency:
    def test_no_planning_dir_returns_empty(self, conn, tmp_path):
        findings = check_artifact_consistency(conn, tmp_path)
        assert findings == []

    def test_extra_artifact_dir_flagged_as_info(self, conn, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        phases_dir.mkdir(parents=True)
        (phases_dir / "99-old-feature").mkdir()
        findings = check_artifact_consistency(conn, tmp_path)
        assert any(
            f["level"] == "info" and "99-old-feature" in f["message"] for f in findings
        )

    def test_executing_phase_without_dir_warns(self, conn, tmp_path):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Build API")
        # Advance to executing
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        transition_phase(conn, ph["id"], "executing")
        phases_dir = tmp_path / ".planning" / "phases"
        phases_dir.mkdir(parents=True)
        findings = check_artifact_consistency(conn, tmp_path)
        assert any(f["level"] == "warning" and "Build API" in f["message"] for f in findings)

    def test_executing_phase_with_matching_dir_passes(self, conn, tmp_path):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Build API")
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        transition_phase(conn, ph["id"], "executing")
        phases_dir = tmp_path / ".planning" / "phases"
        (phases_dir / "01-build-api").mkdir(parents=True)
        findings = check_artifact_consistency(conn, tmp_path)
        assert not any(
            f["level"] == "warning" and "Build API" in f["message"] for f in findings
        )


# ── Stuck phases ──────────────────────────────────────────────────────────────


class TestStuckPhases:
    def test_no_phases_returns_empty(self, conn):
        assert check_stuck_phases(conn) == []

    def test_fresh_executing_phase_not_flagged(self, conn):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Phase 1")
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        transition_phase(conn, ph["id"], "executing")
        findings = check_stuck_phases(conn, stuck_threshold_hours=4)
        assert findings == []

    def test_stale_executing_phase_flagged(self, conn):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Stale Phase")
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        transition_phase(conn, ph["id"], "executing")
        # Backdate started_at to 10 hours ago
        conn.execute(
            "UPDATE phase SET started_at = datetime('now', '-10 hours') WHERE id = ?",
            (ph["id"],),
        )
        conn.commit()
        findings = check_stuck_phases(conn, stuck_threshold_hours=4)
        assert len(findings) == 1
        assert findings[0]["level"] == "warning"
        assert findings[0]["phase_id"] == ph["id"]
        assert findings[0]["age_hours"] >= 9.9

    def test_custom_threshold_respected(self, conn):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Phase 1")
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        transition_phase(conn, ph["id"], "executing")
        conn.execute(
            "UPDATE phase SET started_at = datetime('now', '-3 hours') WHERE id = ?",
            (ph["id"],),
        )
        conn.commit()
        assert check_stuck_phases(conn, stuck_threshold_hours=4) == []
        assert len(check_stuck_phases(conn, stuck_threshold_hours=2)) == 1


# ── Repair ────────────────────────────────────────────────────────────────────


class TestRepair:
    def test_repair_orphaned_plan(self, conn):
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO plan (phase_id, sequence, name, description) VALUES (9999, 1, 'Ghost', 'x')"
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        findings = check_orphaned_rows(conn)
        messages = repair(conn, findings)
        assert any("Deleted orphaned plan" in m for m in messages)
        remaining = conn.execute("SELECT id FROM plan WHERE phase_id = 9999").fetchall()
        assert remaining == []

    def test_repair_stuck_phase_reverts_to_planned_out(self, conn):
        m = create_milestone(conn, "M1", "Milestone 1")
        ph = create_phase(conn, m["id"], "Stuck Phase")
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        transition_phase(conn, ph["id"], "executing")
        conn.execute(
            "UPDATE phase SET started_at = datetime('now', '-10 hours') WHERE id = ?",
            (ph["id"],),
        )
        conn.commit()
        findings = check_stuck_phases(conn, stuck_threshold_hours=4)
        messages = repair(conn, findings)
        assert any("Reverted stuck phase" in m for m in messages)
        row = conn.execute("SELECT status, started_at FROM phase WHERE id = ?", (ph["id"],)).fetchone()
        assert row["status"] == "planned_out"
        assert row["started_at"] is None

    def test_repair_no_action_findings_skipped(self, conn):
        findings = [{"level": "info", "check": "artifact_consistency", "message": "x"}]
        messages = repair(conn, findings)
        assert messages == []


# ── run_health_check ──────────────────────────────────────────────────────────


class TestRunHealthCheck:
    def test_no_db_returns_no_db_status(self, tmp_path):
        result = run_health_check(tmp_path)
        assert result["status"] == "no_db"

    def test_clean_project_returns_ok(self, tmp_path):
        from scripts.db import init
        init(tmp_path)
        result = run_health_check(tmp_path)
        assert result["status"] == "ok"
        assert result["errors"] == 0
        assert result["warnings"] == 0

    def test_repair_flag_applied(self, tmp_path):
        from scripts.db import get_db_path, init, open_project
        from scripts.state import create_milestone, create_project, create_phase, transition_phase
        init(tmp_path)
        with open_project(tmp_path) as c:
            create_project(c, "Test", str(tmp_path))
            m = create_milestone(c, "M1", "Milestone 1")
            ph = create_phase(c, m["id"], "Stuck")
            transition_phase(c, ph["id"], "context_gathered")
            transition_phase(c, ph["id"], "planned_out")
            transition_phase(c, ph["id"], "executing")
            c.execute(
                "UPDATE phase SET started_at = datetime('now', '-10 hours') WHERE id = ?",
                (ph["id"],),
            )

        result = run_health_check(tmp_path, do_repair=True, stuck_threshold_hours=4)
        assert result["status"] == "ok"
        assert len(result["repair_log"]) >= 1
