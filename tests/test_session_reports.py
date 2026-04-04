#!/usr/bin/env python3
"""Tests for Meridian session reports."""

from scripts.session_reports import (
    estimate_token_usage,
    format_session_report,
    generate_session_report,
    get_recent_events,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
    transition_phase,
    transition_plan,
)


def _ms(db):
    create_project(db, name="Test", repo_path="/tmp/test")
    ms = create_milestone(db, "v1", "V1", project_id="default")
    transition_milestone(db, ms["id"], "active")
    return ms


class TestGetRecentEvents:
    def test_returns_events(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "A", "desc")
        transition_phase(db, p["id"], "context_gathered")

        events = get_recent_events(db, hours=1)
        assert len(events) >= 1

    def test_empty_when_no_events(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        events = get_recent_events(db, hours=0)
        assert events == []


class TestGenerateSessionReport:
    def test_counts_plans_completed(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "A", "desc")
        transition_phase(db, p["id"], "context_gathered")
        transition_phase(db, p["id"], "planned_out")
        transition_phase(db, p["id"], "executing")
        plan = create_plan(db, p["id"], "P1", "do thing")
        transition_plan(db, plan["id"], "executing")
        transition_plan(db, plan["id"], "complete")

        report = generate_session_report(db)
        assert report["plans_completed"] >= 1

    def test_report_structure(self, db):
        _ms(db)
        report = generate_session_report(db)
        assert "period" in report
        assert "plans_completed" in report
        assert "phases_advanced" in report
        assert "events" in report


class TestEstimateTokenUsage:
    def test_plan_events(self):
        events = [
            {"entity_type": "plan", "new_status": "complete"},
            {"entity_type": "plan", "new_status": "complete"},
        ]
        estimate = estimate_token_usage(events)
        assert estimate["estimated_input_tokens"] == 100_000
        assert estimate["estimated_total"] > 100_000

    def test_empty_events(self):
        estimate = estimate_token_usage([])
        assert estimate["estimated_total"] == 0

    def test_mixed_events(self):
        events = [
            {"entity_type": "plan", "new_status": "complete"},
            {"entity_type": "review", "new_status": "pass"},
        ]
        estimate = estimate_token_usage(events)
        assert estimate["estimated_input_tokens"] == 70_000


class TestFormatSessionReport:
    def test_markdown_output(self):
        report = {
            "period": "2026-04-04 — now",
            "plans_completed": 3,
            "phases_advanced": 1,
            "decisions_made": 2,
            "events": [],
            "next_action": "Run /meridian:execute",
        }
        tokens = {
            "estimated_input_tokens": 50_000,
            "estimated_output_tokens": 15_000,
            "estimated_total": 65_000,
        }
        output = format_session_report(report, tokens)
        assert "# Session Report" in output
        assert "Plans completed: **3**" in output
        assert "Suggested Next Action" in output
