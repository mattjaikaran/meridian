#!/usr/bin/env python3
"""Tests for cross-model review (scripts/cross_review.py)."""

from unittest.mock import patch

from scripts.cross_review import (
    build_review_prompt,
    compare_findings,
    detect_models,
    format_comparison,
    parse_findings,
    run_external_review,
)


# ── Model Detection Tests ────────────────────────────────────────────────────


class TestDetectModels:
    def test_returns_list(self):
        result = detect_models()
        assert isinstance(result, list)

    def test_model_structure(self):
        with patch("scripts.cross_review.shutil.which", return_value="/usr/bin/codex"):
            result = detect_models()
            found = [m for m in result if m["id"] == "codex"]
            assert len(found) >= 1
            assert "binary" in found[0]
            assert "name" in found[0]

    def test_missing_model_excluded(self):
        with patch("scripts.cross_review.shutil.which", return_value=None):
            result = detect_models()
            assert len(result) == 0

    def test_multiple_models(self):
        def mock_which(binary):
            return f"/usr/bin/{binary}" if binary in ("codex", "gemini") else None

        with patch("scripts.cross_review.shutil.which", side_effect=mock_which):
            result = detect_models()
            ids = [m["id"] for m in result]
            assert "codex" in ids
            assert "gemini" in ids
            assert "aider" not in ids


# ── Prompt Building Tests ────────────────────────────────────────────────────


class TestBuildReviewPrompt:
    def test_basic_prompt(self):
        prompt = build_review_prompt(["src/main.py", "src/utils.py"])
        assert "src/main.py" in prompt
        assert "src/utils.py" in prompt
        assert "code reviewer" in prompt.lower()

    def test_with_context(self):
        prompt = build_review_prompt(
            ["app.py"],
            phase_name="Auth Module",
            phase_description="JWT-based auth",
            acceptance_criteria="Login works",
        )
        assert "Auth Module" in prompt
        assert "JWT-based auth" in prompt
        assert "Login works" in prompt

    def test_empty_files(self):
        prompt = build_review_prompt([])
        assert "Files to review" in prompt

    def test_includes_severity_request(self):
        prompt = build_review_prompt(["f.py"])
        assert "critical" in prompt.lower()
        assert "warning" in prompt.lower()


# ── External Review Tests ────────────────────────────────────────────────────


class TestRunExternalReview:
    def test_unsupported_model(self):
        result = run_external_review("unknown_model", "review this")
        assert result["success"] is False
        assert "Unsupported" in result["error"]

    def test_model_not_installed(self):
        with patch("scripts.cross_review.shutil.which", return_value=None):
            result = run_external_review("codex", "review this")
            assert result["success"] is False
            assert "not installed" in result["error"]

    def test_successful_review(self):
        mock_result = type("Result", (), {"stdout": "No issues found.", "stderr": "", "returncode": 0})()
        with patch("scripts.cross_review.shutil.which", return_value="/usr/bin/codex"), \
             patch("scripts.cross_review.subprocess.run", return_value=mock_result):
            result = run_external_review("codex", "review this")
            assert result["success"] is True
            assert "No issues found" in result["output"]

    def test_failed_review(self):
        mock_result = type("Result", (), {"stdout": "", "stderr": "Error occurred", "returncode": 1})()
        with patch("scripts.cross_review.shutil.which", return_value="/usr/bin/codex"), \
             patch("scripts.cross_review.subprocess.run", return_value=mock_result):
            result = run_external_review("codex", "review this")
            assert result["success"] is False


# ── Finding Parser Tests ─────────────────────────────────────────────────────


class TestParseFindings:
    def test_no_issues(self):
        assert parse_findings("No issues found.") == []

    def test_empty_output(self):
        assert parse_findings("") == []

    def test_parse_file_reference(self):
        output = "Bug in src/main.py:42 - potential null pointer"
        findings = parse_findings(output)
        assert len(findings) >= 1
        assert findings[0]["file"] == "src/main.py"
        assert findings[0]["line"] == 42

    def test_severity_detection(self):
        output = "Critical security issue in auth.py:10 - SQL injection possible"
        findings = parse_findings(output)
        assert len(findings) >= 1
        assert findings[0]["severity"] == "critical"

    def test_warning_severity(self):
        output = "Warning: performance issue in query.py:5 - N+1 query"
        findings = parse_findings(output)
        assert len(findings) >= 1
        assert findings[0]["severity"] == "warning"

    def test_multiple_findings(self):
        output = """Issue in file.py:1 - problem one

Issue in file.py:2 - problem two"""
        findings = parse_findings(output)
        assert len(findings) == 2


# ── Comparison Tests ─────────────────────────────────────────────────────────


class TestCompareFindings:
    def test_no_findings(self):
        result = compare_findings([], [])
        assert result["claude_only"] == []
        assert result["external_only"] == []
        assert result["overlapping"] == []

    def test_claude_only(self):
        claude = [{"file": "a.py", "severity": "critical", "description": "bug"}]
        result = compare_findings(claude, [])
        assert len(result["claude_only"]) == 1
        assert len(result["external_only"]) == 0

    def test_external_only(self):
        external = [{"file": "b.py", "severity": "warning", "description": "perf"}]
        result = compare_findings([], external)
        assert len(result["external_only"]) == 1
        assert len(result["claude_only"]) == 0

    def test_overlapping(self):
        finding = {"file": "c.py", "severity": "info", "description": "style"}
        result = compare_findings([finding], [finding])
        assert len(result["overlapping"]) == 1

    def test_mixed(self):
        claude = [
            {"file": "a.py", "severity": "critical", "description": "bug"},
            {"file": "shared.py", "severity": "warning", "description": "both"},
        ]
        external = [
            {"file": "b.py", "severity": "info", "description": "style"},
            {"file": "shared.py", "severity": "warning", "description": "both too"},
        ]
        result = compare_findings(claude, external)
        assert result["claude_total"] == 2
        assert result["external_total"] == 2


# ── Format Tests ─────────────────────────────────────────────────────────────


class TestFormatComparison:
    def test_empty_comparison(self):
        comparison = {
            "claude_only": [], "external_only": [], "overlapping": [],
            "claude_total": 0, "external_total": 0,
        }
        output = format_comparison(comparison)
        assert "Cross-Model Review" in output
        assert "No findings" in output

    def test_with_findings(self):
        comparison = {
            "claude_only": [{"severity": "critical", "description": "bug in auth"}],
            "external_only": [{"severity": "warning", "description": "slow query"}],
            "overlapping": [],
            "claude_total": 1, "external_total": 1,
        }
        output = format_comparison(comparison, model_name="Codex")
        assert "Claude-Only" in output
        assert "Codex-Only" in output
        assert "bug in auth" in output
        assert "slow query" in output
