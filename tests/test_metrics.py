#!/usr/bin/env python3
"""Tests for Meridian PM metrics engine."""

import pytest

from scripts.metrics import (
    compute_cycle_times,
    compute_progress,
    compute_velocity,
    detect_stalls,
    forecast_completion,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    list_phases,
    transition_milestone,
    transition_phase,
    transition_plan,
)


# ── Velocity Tests ───────────────────────────────────────────────────────────


class TestVelocity:
    def test_no_completed_plans(self, seeded_db):
        result = compute_velocity(seeded_db)
        assert result["velocity"] == 0.0
        assert result["completed_count"] == 0
        assert result["window_days"] == 7

    def test_with_completed_plans(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        # Create and complete plans
        for i in range(3):
            p = create_plan(seeded_db, phase["id"], f"Plan {i}", f"Do {i}")
            transition_plan(seeded_db, p["id"], "executing")
            transition_plan(seeded_db, p["id"], "complete", commit_sha=f"sha{i}")

        result = compute_velocity(seeded_db)
        assert result["completed_count"] == 3
        assert result["velocity"] == round(3 / 7, 2)

    def test_old_completions_excluded(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p = create_plan(seeded_db, phase["id"], "Old plan", "Done long ago")
        transition_plan(seeded_db, p["id"], "executing")
        transition_plan(seeded_db, p["id"], "complete")

        # Manually backdate the completed_at to 10 days ago
        seeded_db.execute(
            "UPDATE plan SET completed_at = datetime('now', '-10 days') WHERE id = ?",
            (p["id"],),
        )
        seeded_db.commit()

        result = compute_velocity(seeded_db)
        assert result["completed_count"] == 0


# ── Cycle Time Tests ─────────────────────────────────────────────────────────


class TestCycleTimes:
    def test_no_completed(self, seeded_db):
        result = compute_cycle_times(seeded_db)
        assert result["phase_avg_hours"] is None
        assert result["plan_avg_hours"] is None

    def test_with_completed_plan(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p = create_plan(seeded_db, phase["id"], "Plan 1", "Do it")
        transition_plan(seeded_db, p["id"], "executing")
        # Backdate started_at by 2 hours
        seeded_db.execute(
            "UPDATE plan SET started_at = datetime('now', '-2 hours') WHERE id = ?",
            (p["id"],),
        )
        seeded_db.commit()
        transition_plan(seeded_db, p["id"], "complete")

        result = compute_cycle_times(seeded_db)
        assert result["plans_sampled"] == 1
        assert result["plan_avg_hours"] is not None
        assert result["plan_avg_hours"] > 0

    def test_with_completed_phase(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")
        # Backdate started_at
        seeded_db.execute(
            "UPDATE phase SET started_at = datetime('now', '-5 hours') WHERE id = ?",
            (pid,),
        )
        seeded_db.commit()
        transition_phase(seeded_db, pid, "verifying")
        transition_phase(seeded_db, pid, "reviewing")
        transition_phase(seeded_db, pid, "complete")

        result = compute_cycle_times(seeded_db)
        assert result["phases_sampled"] == 1
        assert result["phase_avg_hours"] is not None


# ── Stall Detection Tests ────────────────────────────────────────────────────


class TestStalls:
    def test_no_stalls(self, seeded_db):
        stalls = detect_stalls(seeded_db)
        assert stalls == []

    def test_stalled_plan(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")

        p = create_plan(seeded_db, pid, "Stuck plan", "This is stuck")
        transition_plan(seeded_db, p["id"], "executing")
        # Backdate started_at by 30 hours
        seeded_db.execute(
            "UPDATE plan SET started_at = datetime('now', '-30 hours') WHERE id = ?",
            (p["id"],),
        )
        seeded_db.commit()

        stalls = detect_stalls(seeded_db, plan_threshold_hours=24.0)
        assert len(stalls) >= 1
        plan_stalls = [s for s in stalls if s["entity_type"] == "plan"]
        assert len(plan_stalls) == 1
        assert plan_stalls[0]["name"] == "Stuck plan"
        assert plan_stalls[0]["stuck_hours"] > 24

    def test_stalled_phase(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")
        # Backdate started_at by 72 hours
        seeded_db.execute(
            "UPDATE phase SET started_at = datetime('now', '-72 hours') WHERE id = ?",
            (pid,),
        )
        seeded_db.commit()

        stalls = detect_stalls(seeded_db, phase_threshold_hours=48.0)
        phase_stalls = [s for s in stalls if s["entity_type"] == "phase"]
        assert len(phase_stalls) == 1
        assert phase_stalls[0]["stuck_hours"] > 48

    def test_not_stalled_within_threshold(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")

        p = create_plan(seeded_db, pid, "Fresh plan", "Just started")
        transition_plan(seeded_db, p["id"], "executing")

        stalls = detect_stalls(seeded_db, plan_threshold_hours=24.0)
        plan_stalls = [s for s in stalls if s["entity_type"] == "plan"]
        assert len(plan_stalls) == 0


# ── Forecast Tests ───────────────────────────────────────────────────────────


class TestForecast:
    def test_no_milestone(self, db):
        create_project(db, name="App", repo_path="/tmp")
        result = forecast_completion(db)
        assert result["remaining_plans"] == 0
        assert result["eta_days"] is None

    def test_all_complete(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p = create_plan(seeded_db, phase["id"], "Plan", "Do it")
        transition_plan(seeded_db, p["id"], "executing")
        transition_plan(seeded_db, p["id"], "complete")

        result = forecast_completion(seeded_db)
        # Only 1 plan, it's complete; phase 2 has no plans
        assert result["remaining_plans"] == 0
        assert result["eta_days"] == 0.0

    def test_with_remaining_plans(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        # Create 5 plans, complete 2
        for i in range(5):
            p = create_plan(seeded_db, phase["id"], f"Plan {i}", f"Do {i}")
            if i < 2:
                transition_plan(seeded_db, p["id"], "executing")
                transition_plan(seeded_db, p["id"], "complete")

        result = forecast_completion(seeded_db)
        assert result["remaining_plans"] == 3
        # Velocity is 2/7 for 7-day window
        if result["velocity"] > 0:
            assert result["eta_days"] is not None
            assert result["eta_date"] is not None


# ── Progress Tests ───────────────────────────────────────────────────────────


class TestProgress:
    def test_no_milestone(self, db):
        create_project(db, name="App", repo_path="/tmp")
        result = compute_progress(db)
        assert result["milestone"] is None
        assert result["phases"] == []

    def test_empty_phases(self, seeded_db):
        result = compute_progress(seeded_db)
        assert result["milestone"]["name"] == "Version 1.0"
        assert result["milestone"]["pct"] == 0
        assert len(result["phases"]) == 2

    def test_partial_completion(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        # 4 plans, complete 2
        for i in range(4):
            p = create_plan(seeded_db, phase["id"], f"Plan {i}", f"Do {i}")
            if i < 2:
                transition_plan(seeded_db, p["id"], "executing")
                transition_plan(seeded_db, p["id"], "complete")

        result = compute_progress(seeded_db)
        # Phase 1: 2/4 = 50%, Phase 2: 0/0 = 0%
        assert result["phases"][0]["pct"] == 50
        assert result["phases"][0]["done"] == 2
        assert result["phases"][0]["total"] == 4
        # Overall: 2/4 = 50%
        assert result["milestone"]["pct"] == 50

    def test_skipped_counts_as_done(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p1 = create_plan(seeded_db, phase["id"], "Plan 1", "Do 1")
        p2 = create_plan(seeded_db, phase["id"], "Plan 2", "Do 2")
        transition_plan(seeded_db, p1["id"], "executing")
        transition_plan(seeded_db, p1["id"], "complete")
        transition_plan(seeded_db, p2["id"], "skipped")

        result = compute_progress(seeded_db)
        assert result["phases"][0]["pct"] == 100
        assert result["phases"][0]["done"] == 2

    def test_complete_phase_no_plans(self, seeded_db):
        """A phase marked complete with no plans should show 100%."""
        phases = list_phases(seeded_db, "v1.0")
        pid = phases[0]["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")
        transition_phase(seeded_db, pid, "verifying")
        transition_phase(seeded_db, pid, "reviewing")
        transition_phase(seeded_db, pid, "complete")

        result = compute_progress(seeded_db)
        assert result["phases"][0]["pct"] == 100


class TestSettingsBasedThresholds:
    def test_velocity_uses_setting(self, seeded_db):
        from scripts.state import set_setting
        set_setting(seeded_db, "velocity_window_days", "14")
        result = compute_velocity(seeded_db)
        assert result["window_days"] == 14

    def test_stalls_uses_settings(self, seeded_db):
        from scripts.state import set_setting
        set_setting(seeded_db, "stall_plan_hours", "12")
        set_setting(seeded_db, "stall_phase_hours", "24")
        # Just verifying it runs without error with settings
        stalls = detect_stalls(seeded_db)
        assert isinstance(stalls, list)
