#!/usr/bin/env python3
"""Tests for Meridian codebase mapping."""

from scripts.codebase_mapping import (
    ANALYSIS_DOMAINS,
    generate_analysis_prompt,
    generate_scan_summary,
    load_analysis,
    plan_codebase_scan,
    save_analysis,
)


class TestAnalysisDomains:
    def test_seven_domains(self):
        assert len(ANALYSIS_DOMAINS) == 7

    def test_each_has_name_and_focus(self):
        for d in ANALYSIS_DOMAINS:
            assert "name" in d
            assert "focus" in d


class TestGenerateAnalysisPrompt:
    def test_includes_domain(self):
        domain = {"name": "architecture", "focus": "High-level arch"}
        prompt = generate_analysis_prompt(domain, "/tmp/project")
        assert "architecture" in prompt
        assert "/tmp/project" in prompt

    def test_includes_focus(self):
        domain = {"name": "testing", "focus": "Test patterns"}
        prompt = generate_analysis_prompt(domain, "/tmp/p")
        assert "Test patterns" in prompt


class TestPlanCodebaseScan:
    def test_all_domains(self):
        plans = plan_codebase_scan("/tmp/project")
        assert len(plans) == 7
        for p in plans:
            assert "domain" in p
            assert "prompt" in p
            assert "output_file" in p
            assert ".meridian/codebase/" in p["output_file"]

    def test_filtered_domains(self):
        plans = plan_codebase_scan("/tmp/p", domains=["testing", "stack"])
        assert len(plans) == 2
        names = {p["domain"] for p in plans}
        assert names == {"testing", "stack"}

    def test_unknown_domain_filtered(self):
        plans = plan_codebase_scan("/tmp/p", domains=["bogus"])
        assert len(plans) == 0


class TestSaveAndLoadAnalysis:
    def test_save_and_load(self, tmp_path):
        save_analysis(str(tmp_path), "architecture", "# Arch\nSome findings")
        result = load_analysis(str(tmp_path), "architecture")
        assert "architecture" in result
        assert "Some findings" in result["architecture"]

    def test_load_all(self, tmp_path):
        save_analysis(str(tmp_path), "architecture", "arch content")
        save_analysis(str(tmp_path), "testing", "test content")
        result = load_analysis(str(tmp_path))
        assert len(result) == 2

    def test_load_missing(self, tmp_path):
        result = load_analysis(str(tmp_path), "nonexistent")
        assert result == {}

    def test_load_empty_dir(self, tmp_path):
        result = load_analysis(str(tmp_path))
        assert result == {}


class TestGenerateScanSummary:
    def test_with_analyses(self):
        analyses = {"architecture": "# Arch", "testing": "# Tests"}
        summary = generate_scan_summary(analyses)
        assert "# Codebase Scan Summary" in summary
        assert "Architecture" in summary
        assert "Testing" in summary

    def test_empty(self):
        summary = generate_scan_summary({})
        assert "No analyses available" in summary
