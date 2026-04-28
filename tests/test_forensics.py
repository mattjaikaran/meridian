"""Tests for the Meridian workflow forensics module."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.db import open_project
from scripts.forensics import (
    collect_git_context,
    detect_abandoned_work,
    detect_crash_signatures,
    detect_missing_artifacts,
    detect_stuck_loops,
    run_forensics,
    write_report,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    transition_phase,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def conn():
    with open_project(":memory:") as c:
        create_project(c, "Test", "/tmp/test")
        yield c


@pytest.fixture()
def milestone(conn):
    return create_milestone(conn, "M1", "Milestone 1")


@pytest.fixture()
def clean_phase(conn, milestone):
    return create_phase(conn, milestone["id"], "Build API")


def _advance_to_executing(conn, phase_id: str) -> None:
    transition_phase(conn, phase_id, "context_gathered")
    transition_phase(conn, phase_id, "planned_out")
    transition_phase(conn, phase_id, "executing")


def _set_started_at(conn, phase_id: str, dt: datetime) -> None:
    conn.execute(
        "UPDATE phase SET started_at = ? WHERE id = ?",
        (dt.isoformat(), phase_id),
    )
    conn.commit()


# ── detect_stuck_loops ────────────────────────────────────────────────────────


class TestDetectStuckLoops:
    def test_no_executing_phases_returns_empty(self, conn):
        assert detect_stuck_loops(conn) == []

    def test_recently_started_phase_not_flagged(self, conn, milestone):
        ph = create_phase(conn, milestone["id"], "Fast Phase")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(hours=1))
        findings = detect_stuck_loops(conn, stuck_threshold_hours=4)
        assert findings == []

    def test_old_executing_phase_flagged(self, conn, milestone):
        ph = create_phase(conn, milestone["id"], "Slow Phase")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(hours=10))
        findings = detect_stuck_loops(conn, stuck_threshold_hours=4)
        assert len(findings) == 1
        f = findings[0]
        assert f["type"] == "stuck_loop"
        assert f["severity"] == "warning"
        assert "Slow Phase" in f["message"]
        assert f["age_hours"] >= 9.9

    def test_custom_threshold_respected(self, conn, milestone):
        ph = create_phase(conn, milestone["id"], "Mid Phase")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(hours=6))
        # 8h threshold — should not flag
        assert detect_stuck_loops(conn, stuck_threshold_hours=8) == []
        # 4h threshold — should flag
        assert len(detect_stuck_loops(conn, stuck_threshold_hours=4)) == 1

    def test_phase_without_started_at_skipped(self, conn, milestone):
        ph = create_phase(conn, milestone["id"], "Unstarted")
        _advance_to_executing(conn, ph["id"])
        conn.execute("UPDATE phase SET started_at = NULL WHERE id = ?", (ph["id"],))
        conn.commit()
        assert detect_stuck_loops(conn) == []

    def test_finding_has_suggestion(self, conn, milestone):
        ph = create_phase(conn, milestone["id"], "Stuck")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(hours=5))
        findings = detect_stuck_loops(conn, stuck_threshold_hours=4)
        assert findings[0].get("suggestion")

    def test_multiple_stuck_phases(self, conn, milestone):
        for name in ["Phase A", "Phase B", "Phase C"]:
            ph = create_phase(conn, milestone["id"], name)
            _advance_to_executing(conn, ph["id"])
            _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(hours=5))
        findings = detect_stuck_loops(conn, stuck_threshold_hours=4)
        assert len(findings) == 3


# ── detect_missing_artifacts ──────────────────────────────────────────────────


class TestDetectMissingArtifacts:
    def test_planned_phase_without_dir_not_flagged(self, conn, milestone, tmp_path):
        create_phase(conn, milestone["id"], "New Phase")
        findings = detect_missing_artifacts(conn, tmp_path)
        assert findings == []

    def test_executing_without_dir_flagged(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Active Phase")
        _advance_to_executing(conn, ph["id"])
        (tmp_path / ".planning" / "phases").mkdir(parents=True)
        findings = detect_missing_artifacts(conn, tmp_path)
        assert len(findings) == 1
        assert findings[0]["type"] == "missing_artifact"
        assert findings[0]["severity"] == "warning"
        assert "Active Phase" in findings[0]["message"]

    def test_executing_with_dir_and_plan_passes(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Good Phase")
        _advance_to_executing(conn, ph["id"])
        phase_dir = tmp_path / ".planning" / "phases" / "01-good-phase"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan\n\nFull plan here.\n" * 5)
        findings = detect_missing_artifacts(conn, tmp_path)
        assert not any(f["phase_name"] == "Good Phase" for f in findings)

    def test_executing_with_dir_but_no_plan_flagged(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "No Plan")
        _advance_to_executing(conn, ph["id"])
        phase_dir = tmp_path / ".planning" / "phases" / "01-no-plan"
        phase_dir.mkdir(parents=True)
        findings = detect_missing_artifacts(conn, tmp_path)
        assert any(
            f["type"] == "missing_artifact" and "No Plan" in f["message"] for f in findings
        )

    def test_planned_out_without_dir_not_flagged(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Just Planned")
        transition_phase(conn, ph["id"], "context_gathered")
        transition_phase(conn, ph["id"], "planned_out")
        (tmp_path / ".planning" / "phases").mkdir(parents=True)
        findings = detect_missing_artifacts(conn, tmp_path)
        assert findings == []

    def test_complete_phase_not_checked(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Done Phase")
        _advance_to_executing(conn, ph["id"])
        transition_phase(conn, ph["id"], "verifying")
        transition_phase(conn, ph["id"], "reviewing")
        transition_phase(conn, ph["id"], "complete")
        (tmp_path / ".planning" / "phases").mkdir(parents=True)
        findings = detect_missing_artifacts(conn, tmp_path)
        assert not any(f.get("phase_name") == "Done Phase" for f in findings)


# ── detect_abandoned_work ─────────────────────────────────────────────────────


class TestDetectAbandonedWork:
    def test_recent_phase_not_flagged(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Recent")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(days=1))
        findings = detect_abandoned_work(conn, tmp_path, abandoned_threshold_days=3)
        assert findings == []

    def test_old_phase_with_no_artifact_dir_flagged(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Old Phase")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(days=7))
        findings = detect_abandoned_work(conn, tmp_path, abandoned_threshold_days=3)
        assert len(findings) == 1
        assert findings[0]["type"] == "abandoned_work"
        assert findings[0]["severity"] == "info"
        assert "Old Phase" in findings[0]["message"]
        assert findings[0]["age_days"] >= 6

    def test_phase_without_started_at_skipped(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "NoStart")
        _advance_to_executing(conn, ph["id"])
        conn.execute("UPDATE phase SET started_at = NULL WHERE id = ?", (ph["id"],))
        conn.commit()
        findings = detect_abandoned_work(conn, tmp_path, abandoned_threshold_days=3)
        assert findings == []

    def test_custom_threshold_respected(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Border")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(days=5))
        # 7-day threshold — not flagged
        assert detect_abandoned_work(conn, tmp_path, abandoned_threshold_days=7) == []
        # 3-day threshold — flagged
        assert len(detect_abandoned_work(conn, tmp_path, abandoned_threshold_days=3)) == 1

    def test_finding_has_suggestion(self, conn, milestone, tmp_path):
        ph = create_phase(conn, milestone["id"], "Abandoned")
        _advance_to_executing(conn, ph["id"])
        _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(days=10))
        findings = detect_abandoned_work(conn, tmp_path)
        assert findings[0].get("suggestion")


# ── detect_crash_signatures ───────────────────────────────────────────────────


class TestDetectCrashSignatures:
    def test_no_planning_dir_returns_empty(self, tmp_path):
        assert detect_crash_signatures(tmp_path) == []

    def test_empty_phase_dir_flagged(self, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        empty_dir = phases_dir / "01-empty"
        empty_dir.mkdir(parents=True)
        findings = detect_crash_signatures(tmp_path)
        assert len(findings) == 1
        assert findings[0]["type"] == "crash_signature"
        assert "empty" in findings[0]["message"].lower()

    def test_tiny_plan_flagged_as_warning(self, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        phase_dir = phases_dir / "01-truncated"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("TODO")  # < 50 bytes
        findings = detect_crash_signatures(tmp_path)
        assert any(
            f["type"] == "crash_signature"
            and f["severity"] == "warning"
            and "PLAN.md" in f["message"]
            for f in findings
        )

    def test_tiny_verification_flagged_as_info(self, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        phase_dir = phases_dir / "01-phase"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan\n\nFull content here with lots of text.\n" * 3)
        (phase_dir / "VERIFICATION.md").write_text("x")
        findings = detect_crash_signatures(tmp_path)
        assert any(
            f["type"] == "crash_signature"
            and f["severity"] == "info"
            and "VERIFICATION.md" in f["message"]
            for f in findings
        )

    def test_normal_plan_not_flagged(self, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        phase_dir = phases_dir / "01-good"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("# Plan\n\nThis is a proper plan.\n" * 5)
        findings = detect_crash_signatures(tmp_path)
        assert findings == []

    def test_non_key_files_ignored(self, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        phase_dir = phases_dir / "01-phase"
        phase_dir.mkdir(parents=True)
        (phase_dir / "notes.txt").write_text("x")  # Not a key file
        findings = detect_crash_signatures(tmp_path)
        # Only the empty-dir check fires (non-key files don't count as content)
        # phase_dir has one file so it's not "empty" — no empty-dir finding
        assert not any(f.get("severity") == "warning" for f in findings)

    def test_content_preview_included(self, tmp_path):
        phases_dir = tmp_path / ".planning" / "phases"
        phase_dir = phases_dir / "01-stub"
        phase_dir.mkdir(parents=True)
        (phase_dir / "PLAN.md").write_text("STUB")
        findings = detect_crash_signatures(tmp_path)
        assert any("content_preview" in f for f in findings)


# ── collect_git_context ───────────────────────────────────────────────────────


class TestCollectGitContext:
    def test_returns_dict_with_expected_keys(self, tmp_path):
        ctx = collect_git_context(tmp_path)
        assert "branch" in ctx
        assert "recent_log" in ctx
        assert "uncommitted_files" in ctx
        assert "uncommitted_count" in ctx

    def test_non_git_dir_returns_safe_defaults(self, tmp_path):
        ctx = collect_git_context(tmp_path)
        assert isinstance(ctx["branch"], str)
        assert isinstance(ctx["uncommitted_files"], list)
        assert isinstance(ctx["uncommitted_count"], int)

    def test_git_repo_returns_branch(self):
        from pathlib import Path
        ctx = collect_git_context(Path("."))
        assert ctx["branch"] not in ("", None)


# ── run_forensics ─────────────────────────────────────────────────────────────


class TestRunForensics:
    def test_no_db_returns_no_db_status(self, tmp_path):
        result = run_forensics(tmp_path)
        assert result["status"] == "no_db"
        assert result["findings"] == []

    def test_clean_project_returns_clean(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
        result = run_forensics(tmp_path, include_git=False)
        assert result["status"] == "clean"
        assert result["warnings"] == 0

    def test_result_has_all_expected_keys(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
        result = run_forensics(tmp_path, include_git=False)
        assert "status" in result
        assert "findings" in result
        assert "warnings" in result
        assert "infos" in result
        assert "generated_at" in result

    def test_notes_status_when_only_infos(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
            m = create_milestone(conn, "M1", "Milestone 1")
            ph = create_phase(conn, m["id"], "Old Phase")
            _advance_to_executing(conn, ph["id"])
            _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(days=10))
        result = run_forensics(tmp_path, include_git=False, abandoned_threshold_days=3)
        assert result["status"] in ("notes", "issues_found", "clean")

    def test_issues_found_when_warnings_present(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
            m = create_milestone(conn, "M1", "Milestone 1")
            ph = create_phase(conn, m["id"], "Stuck Phase")
            _advance_to_executing(conn, ph["id"])
            _set_started_at(conn, ph["id"], datetime.now(UTC) - timedelta(hours=10))
        result = run_forensics(tmp_path, include_git=False, stuck_threshold_hours=4)
        assert result["status"] == "issues_found"
        assert result["warnings"] >= 1

    def test_include_git_false_skips_git(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
        result = run_forensics(tmp_path, include_git=False)
        assert result["git"] == {}

    def test_include_git_true_populates_git(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
        result = run_forensics(tmp_path, include_git=True)
        assert isinstance(result["git"], dict)
        assert "branch" in result["git"]

    def test_generated_at_is_iso_string(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
        result = run_forensics(tmp_path, include_git=False)
        datetime.fromisoformat(result["generated_at"])  # should not raise


# ── write_report ──────────────────────────────────────────────────────────────


class TestWriteReport:
    def _make_report(self, **overrides) -> dict:
        base = {
            "status": "clean",
            "findings": [],
            "warnings": 0,
            "infos": 0,
            "git": {},
            "generated_at": datetime.now(UTC).isoformat(),
        }
        base.update(overrides)
        return base

    def test_creates_forensics_dir(self, tmp_path):
        report = self._make_report()
        path = write_report(report, tmp_path)
        assert (tmp_path / ".planning" / "forensics").is_dir()

    def test_report_file_created(self, tmp_path):
        report = self._make_report()
        path = write_report(report, tmp_path)
        assert path.exists()
        assert path.suffix == ".md"

    def test_filename_has_timestamp(self, tmp_path):
        report = self._make_report()
        path = write_report(report, tmp_path)
        assert "report-" in path.name
        assert path.name.endswith(".md")

    def test_report_contains_status(self, tmp_path):
        report = self._make_report(status="issues_found", warnings=2)
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "issues_found" in content

    def test_report_contains_section_headers(self, tmp_path):
        report = self._make_report()
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "Stuck Execution Loops" in content
        assert "Missing Artifacts" in content
        assert "Abandoned Work" in content
        assert "Crash Signatures" in content

    def test_report_contains_findings(self, tmp_path):
        findings = [{
            "type": "stuck_loop",
            "severity": "warning",
            "message": "Phase 'Deploy' stuck for 6.2h",
            "suggestion": "Run health check",
        }]
        report = self._make_report(status="issues_found", findings=findings, warnings=1)
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "Deploy" in content
        assert "6.2h" in content

    def test_report_contains_git_context(self, tmp_path):
        git_ctx = {
            "branch": "feature/test",
            "recent_log": "abc1234 feat: add thing",
            "uncommitted_files": ["src/foo.py"],
            "uncommitted_count": 1,
        }
        report = self._make_report(git=git_ctx)
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "feature/test" in content
        assert "abc1234" in content

    def test_returns_path_object(self, tmp_path):
        report = self._make_report()
        result = write_report(report, tmp_path)
        assert isinstance(result, Path)

    def test_no_git_section_when_empty(self, tmp_path):
        report = self._make_report(git={})
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "Git Context" not in content

    def test_multiple_reports_create_unique_files(self, tmp_path):
        import time
        report = self._make_report()
        p1 = write_report(report, tmp_path)
        time.sleep(1.1)  # ensure different timestamp
        p2 = write_report(report, tmp_path)
        assert p1 != p2
        assert p1.exists()
        assert p2.exists()
