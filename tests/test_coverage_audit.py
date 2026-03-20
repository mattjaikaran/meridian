#!/usr/bin/env python3
"""Tests for test coverage audit (scripts/coverage_audit.py)."""

from pathlib import Path

from scripts.coverage_audit import audit_test_coverage, format_coverage_report


class TestAuditCoverage:
    def test_full_coverage(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()
        (scripts / "db.py").write_text("")
        (scripts / "state.py").write_text("")
        (tests / "test_db.py").write_text("")
        (tests / "test_state.py").write_text("")

        result = audit_test_coverage(scripts, tests)
        assert result["coverage_pct"] == 100.0
        assert len(result["uncovered"]) == 0
        assert len(result["covered"]) == 2

    def test_partial_coverage(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()
        (scripts / "db.py").write_text("")
        (scripts / "state.py").write_text("")
        (scripts / "metrics.py").write_text("")
        (tests / "test_db.py").write_text("")

        result = audit_test_coverage(scripts, tests)
        assert result["coverage_pct"] < 100.0
        assert len(result["uncovered"]) == 2
        assert len(result["covered"]) == 1

    def test_no_scripts(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()

        result = audit_test_coverage(scripts, tests)
        assert result["coverage_pct"] == 0.0
        assert result["total_scripts"] == 0

    def test_excludes_init(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()
        (scripts / "__init__.py").write_text("")
        (scripts / "db.py").write_text("")
        (tests / "test_db.py").write_text("")

        result = audit_test_coverage(scripts, tests)
        assert result["total_scripts"] == 1  # __init__ excluded

    def test_orphaned_tests(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()
        (scripts / "db.py").write_text("")
        (tests / "test_db.py").write_text("")
        (tests / "test_nonexistent.py").write_text("")

        result = audit_test_coverage(scripts, tests)
        assert len(result["orphaned_tests"]) == 1
        assert result["orphaned_tests"][0]["test"] == "test_nonexistent.py"

    def test_real_codebase(self):
        """Run against the actual Meridian codebase."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        tests_dir = Path(__file__).parent

        result = audit_test_coverage(scripts_dir, tests_dir)
        assert result["total_scripts"] > 0
        assert result["coverage_pct"] > 50.0  # Should have decent coverage


class TestFormatReport:
    def test_format_full_coverage(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()
        (scripts / "db.py").write_text("")
        (tests / "test_db.py").write_text("")

        result = audit_test_coverage(scripts, tests)
        report = format_coverage_report(result)
        assert "100.0%" in report
        assert "Covered Modules" in report

    def test_format_with_gaps(self, tmp_path):
        scripts = tmp_path / "scripts"
        tests = tmp_path / "tests"
        scripts.mkdir()
        tests.mkdir()
        (scripts / "db.py").write_text("")
        (scripts / "utils.py").write_text("")
        (tests / "test_db.py").write_text("")

        result = audit_test_coverage(scripts, tests)
        report = format_coverage_report(result)
        assert "Uncovered Modules" in report
        assert "utils.py" in report
