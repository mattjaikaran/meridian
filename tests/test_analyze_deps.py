"""Tests for the Meridian dependency analysis module."""

import json
from pathlib import Path

import pytest

from scripts.analyze_deps import (
    apply_suggestions,
    build_suggestions,
    detect_file_overlaps,
    detect_name_references,
    detect_sequence_gaps,
    run_analysis,
    write_report,
)
from scripts.db import open_project
from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def conn():
    with open_project(":memory:") as c:
        create_project(c, "Test", "/tmp/test")
        yield c


@pytest.fixture()
def milestone(conn):
    return create_milestone(conn, "M1", "Test Milestone")


@pytest.fixture()
def two_phases(conn, milestone):
    ph1 = create_phase(conn, milestone["id"], "Build Models", sequence=1)
    ph2 = create_phase(conn, milestone["id"], "Build API", sequence=2)
    return ph1, ph2


# ── detect_file_overlaps ──────────────────────────────────────────────────────


class TestDetectFileOverlaps:
    def test_no_plans_returns_empty(self, conn, milestone):
        create_phase(conn, milestone["id"], "Phase A")
        assert detect_file_overlaps(conn, milestone["id"]) == []

    def test_single_phase_no_overlap(self, conn, milestone, two_phases):
        ph1, _ = two_phases
        create_plan(
            conn, ph1["id"], "Create model", "desc",
            files_to_create=["models/user.py"],
        )
        assert detect_file_overlaps(conn, milestone["id"]) == []

    def test_modifier_after_creator_suggests_dep(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        create_plan(
            conn, ph1["id"], "Create model", "desc",
            files_to_create=["models/user.py"],
        )
        create_plan(
            conn, ph2["id"], "Add endpoint", "desc",
            files_to_modify=["models/user.py"],
        )
        findings = detect_file_overlaps(conn, milestone["id"])
        assert len(findings) == 1
        f = findings[0]
        assert f["type"] == "file_overlap"
        assert f["file"] == "models/user.py"
        assert f["dependent_phase_id"] == ph2["id"]
        assert f["dependency_phase_id"] == ph1["id"]
        assert f["suggested_dep"] == {"phase_id": ph2["id"], "depends_on": ph1["id"]}

    def test_two_creators_same_file_conflict(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        create_plan(conn, ph1["id"], "Create foo", "desc", files_to_create=["foo.py"])
        create_plan(conn, ph2["id"], "Also create foo", "desc", files_to_create=["foo.py"])
        findings = detect_file_overlaps(conn, milestone["id"])
        conflicts = [f for f in findings if f["type"] == "file_conflict"]
        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == "warning"

    def test_modifier_before_creator_is_warning(self, conn, milestone):
        # ph2 (seq=1) modifies a file that ph1 (seq=2) creates — ordering inversion
        ph2 = create_phase(conn, milestone["id"], "Modifier", sequence=1)
        ph1 = create_phase(conn, milestone["id"], "Creator", sequence=2)
        create_plan(conn, ph1["id"], "Create foo", "desc", files_to_create=["foo.py"])
        create_plan(conn, ph2["id"], "Modify foo", "desc", files_to_modify=["foo.py"])
        findings = detect_file_overlaps(conn, milestone["id"])
        overlaps = [f for f in findings if f["type"] == "file_overlap"]
        assert any(f["severity"] == "warning" for f in overlaps)

    def test_different_files_no_overlap(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        create_plan(conn, ph1["id"], "Create A", "desc", files_to_create=["a.py"])
        create_plan(conn, ph2["id"], "Create B", "desc", files_to_create=["b.py"])
        findings = detect_file_overlaps(conn, milestone["id"])
        assert findings == []


# ── detect_name_references ────────────────────────────────────────────────────


class TestDetectNameReferences:
    def test_no_cross_references_returns_empty(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        create_plan(conn, ph1["id"], "Plan A", "do something unrelated")
        assert detect_name_references(conn, milestone["id"]) == []

    def test_phase_name_in_description_detected(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        # ph2's plan description mentions ph1's name "Build Models"
        create_plan(
            conn, ph2["id"], "Extend models",
            "Extend the build models schema to add endpoints",
        )
        findings = detect_name_references(conn, milestone["id"])
        assert any(
            f["referencing_phase_id"] == ph2["id"]
            and f["referenced_phase_id"] == ph1["id"]
            for f in findings
        )

    def test_short_name_not_matched(self, conn, milestone):
        ph1 = create_phase(conn, milestone["id"], "DB", sequence=1)
        ph2 = create_phase(conn, milestone["id"], "Build API", sequence=2)
        # "DB" is < 4 chars, should not match
        create_plan(conn, ph2["id"], "Build endpoint", "add db connection string")
        findings = detect_name_references(conn, milestone["id"])
        assert not any(f["referenced_phase_id"] == ph1["id"] for f in findings)

    def test_suggestion_points_correct_direction(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        create_plan(conn, ph2["id"], "Use models", "use the build models layer")
        findings = detect_name_references(conn, milestone["id"])
        refs = [f for f in findings if f["type"] == "name_reference"]
        assert refs
        assert refs[0]["suggested_dep"]["phase_id"] == ph2["id"]
        assert refs[0]["suggested_dep"]["depends_on"] == ph1["id"]


# ── detect_sequence_gaps ──────────────────────────────────────────────────────


class TestDetectSequenceGaps:
    def test_first_phase_not_flagged(self, conn, milestone):
        create_phase(conn, milestone["id"], "Phase One", sequence=1)
        findings = detect_sequence_gaps(conn, milestone["id"])
        assert findings == []

    def test_second_phase_without_depends_on_flagged(self, conn, milestone, two_phases):
        _, ph2 = two_phases
        findings = detect_sequence_gaps(conn, milestone["id"])
        assert any(f["phase_id"] == ph2["id"] for f in findings)

    def test_phase_with_depends_on_not_flagged(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        conn.execute(
            "UPDATE phase SET depends_on = ? WHERE id = ?",
            (json.dumps([ph1["id"]]), ph2["id"]),
        )
        conn.commit()
        findings = detect_sequence_gaps(conn, milestone["id"])
        assert not any(f["phase_id"] == ph2["id"] for f in findings)


# ── build_suggestions ─────────────────────────────────────────────────────────


class TestBuildSuggestions:
    def test_empty_findings_empty_suggestions(self):
        assert build_suggestions([]) == {}

    def test_single_suggestion_extracted(self):
        findings = [{
            "type": "file_overlap",
            "suggested_dep": {"phase_id": 2, "depends_on": 1},
        }]
        result = build_suggestions(findings)
        assert result == {2: [1]}

    def test_duplicate_suggestions_deduped(self):
        findings = [
            {"type": "file_overlap", "suggested_dep": {"phase_id": 3, "depends_on": 1}},
            {"type": "name_reference", "suggested_dep": {"phase_id": 3, "depends_on": 1}},
        ]
        result = build_suggestions(findings)
        assert result == {3: [1]}

    def test_multiple_deps_merged(self):
        findings = [
            {"type": "file_overlap", "suggested_dep": {"phase_id": 3, "depends_on": 1}},
            {"type": "name_reference", "suggested_dep": {"phase_id": 3, "depends_on": 2}},
        ]
        result = build_suggestions(findings)
        assert result == {3: [1, 2]}

    def test_findings_without_suggested_dep_ignored(self):
        findings = [{"type": "missing_explicit_dep", "phase_id": 2}]
        assert build_suggestions(findings) == {}


# ── apply_suggestions ─────────────────────────────────────────────────────────


class TestApplySuggestions:
    def test_writes_depends_on_to_db(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        applied = apply_suggestions(conn, {ph2["id"]: [ph1["id"]]})
        assert len(applied) == 1
        assert applied[0]["phase_id"] == ph2["id"]
        assert applied[0]["depends_on"] == [ph1["id"]]

        row = conn.execute(
            "SELECT depends_on FROM phase WHERE id = ?", (ph2["id"],)
        ).fetchone()
        assert json.loads(row["depends_on"]) == [ph1["id"]]

    def test_merges_with_existing_deps(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        ph3 = create_phase(conn, milestone["id"], "Phase C", sequence=3)
        # Pre-existing dep: ph2 depends on ph1
        conn.execute(
            "UPDATE phase SET depends_on = ? WHERE id = ?",
            (json.dumps([ph1["id"]]), ph2["id"]),
        )
        conn.commit()
        # Add new dep: ph2 also depends on ph3
        applied = apply_suggestions(conn, {ph2["id"]: [ph3["id"]]})
        assert len(applied) == 1
        assert sorted(applied[0]["depends_on"]) == sorted([ph1["id"], ph3["id"]])

    def test_no_change_skipped(self, conn, milestone, two_phases):
        ph1, ph2 = two_phases
        conn.execute(
            "UPDATE phase SET depends_on = ? WHERE id = ?",
            (json.dumps([ph1["id"]]), ph2["id"]),
        )
        conn.commit()
        applied = apply_suggestions(conn, {ph2["id"]: [ph1["id"]]})
        assert applied == []

    def test_unknown_phase_id_ignored(self, conn, milestone):
        applied = apply_suggestions(conn, {99999: [1]})
        assert applied == []


# ── run_analysis ──────────────────────────────────────────────────────────────


class TestRunAnalysis:
    def test_no_db_returns_no_db_status(self, tmp_path):
        result = run_analysis(tmp_path)
        assert result["status"] == "no_db"

    def test_no_milestones_returns_no_milestone(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
        result = run_analysis(tmp_path)
        assert result["status"] == "no_milestone"

    def test_clean_milestone_no_findings(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
            m = create_milestone(conn, "M1", "Test")
            create_phase(conn, m["id"], "Only Phase", sequence=1)
        result = run_analysis(tmp_path)
        assert result["status"] == "clean"

    def test_file_overlap_detected(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
            m = create_milestone(conn, "M1", "Test")
            ph1 = create_phase(conn, m["id"], "Create Model", sequence=1)
            ph2 = create_phase(conn, m["id"], "Modify Model", sequence=2)
            create_plan(conn, ph1["id"], "P1", "desc", files_to_create=["model.py"])
            create_plan(conn, ph2["id"], "P2", "desc", files_to_modify=["model.py"])
        result = run_analysis(tmp_path)
        assert result["warnings"] > 0 or result["infos"] > 0
        overlaps = [f for f in result["findings"] if f["type"] == "file_overlap"]
        assert len(overlaps) == 1

    def test_apply_writes_to_db(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
            m = create_milestone(conn, "M1", "Test")
            ph1 = create_phase(conn, m["id"], "Creator", sequence=1)
            ph2 = create_phase(conn, m["id"], "Modifier", sequence=2)
            create_plan(conn, ph1["id"], "P1", "desc", files_to_create=["x.py"])
            create_plan(conn, ph2["id"], "P2", "desc", files_to_modify=["x.py"])
        result = run_analysis(tmp_path, apply=True)
        assert result["applied"]
        with open_project(tmp_path) as conn:
            row = conn.execute(
                "SELECT depends_on FROM phase WHERE sequence = 2"
            ).fetchone()
            assert row["depends_on"] is not None

    def test_explicit_milestone_id(self, tmp_path):
        with open_project(tmp_path) as conn:
            create_project(conn, "Test", str(tmp_path))
            m = create_milestone(conn, "M1", "Test")
            create_phase(conn, m["id"], "Solo Phase", sequence=1)
        result = run_analysis(tmp_path, milestone_id=m["id"])
        assert result["milestone_id"] == m["id"]


# ── write_report ──────────────────────────────────────────────────────────────


class TestWriteReport:
    def test_creates_file(self, tmp_path):
        report = {
            "status": "clean",
            "milestone_name": "Test",
            "warnings": 0,
            "infos": 0,
            "findings": [],
            "suggestions": {},
            "applied": [],
            "generated_at": "2026-01-01T00:00:00+00:00",
        }
        path = write_report(report, tmp_path)
        assert path.exists()
        assert path.suffix == ".md"
        assert "deps" in str(path)

    def test_report_contains_milestone(self, tmp_path):
        report = {
            "status": "clean",
            "milestone_name": "Sprint 3",
            "warnings": 0,
            "infos": 0,
            "findings": [],
            "suggestions": {},
            "applied": [],
            "generated_at": "2026-01-01T00:00:00+00:00",
        }
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "Sprint 3" in content

    def test_report_contains_suggestions(self, tmp_path):
        report = {
            "status": "suggestions",
            "milestone_name": "M1",
            "warnings": 0,
            "infos": 1,
            "findings": [],
            "suggestions": {2: [1]},
            "applied": [],
            "generated_at": "2026-01-01T00:00:00+00:00",
        }
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "Suggested depends_on" in content

    def test_report_contains_applied(self, tmp_path):
        report = {
            "status": "suggestions",
            "milestone_name": "M1",
            "warnings": 0,
            "infos": 1,
            "findings": [],
            "suggestions": {},
            "applied": [{"phase_id": 2, "phase_name": "Build API", "depends_on": [1]}],
            "generated_at": "2026-01-01T00:00:00+00:00",
        }
        path = write_report(report, tmp_path)
        content = path.read_text()
        assert "Applied to Database" in content
        assert "Build API" in content
