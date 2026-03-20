#!/usr/bin/env python3
"""Tests for Meridian backlog/seed management."""

import pytest

from scripts.backlog import (
    _next_seed_id,
    _parse_trigger,
    check_triggers,
    dismiss_seed,
    list_seeds,
    plant_seed,
    promote_seed,
)


# ── Helper Tests ─────────────────────────────────────────────────────────────


class TestNextSeedId:
    def test_empty_content(self):
        assert _next_seed_id("") == "SEED-001"

    def test_single_seed(self):
        assert _next_seed_id("[SEED-001] test") == "SEED-002"

    def test_multiple_seeds(self):
        content = "[SEED-001] a\n[SEED-003] b\n[SEED-002] c"
        assert _next_seed_id(content) == "SEED-004"


class TestParseTrigger:
    def test_after_phase(self):
        result = _parse_trigger("after_phase:auth")
        assert result == {"type": "after_phase", "value": "auth"}

    def test_after_milestone(self):
        result = _parse_trigger("after_milestone:v2.0")
        assert result == {"type": "after_milestone", "value": "v2.0"}

    def test_manual(self):
        result = _parse_trigger("manual")
        assert result == {"type": "manual", "value": ""}

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid trigger type"):
            _parse_trigger("invalid:foo")


# ── Plant Tests ──────────────────────────────────────────────────────────────


class TestPlantSeed:
    def test_plant_default_trigger(self, tmp_path):
        result = plant_seed(tmp_path, "Add caching layer")
        assert result["id"] == "SEED-001"
        assert result["idea"] == "Add caching layer"
        assert result["trigger"]["type"] == "manual"
        assert result["status"] == "active"

    def test_plant_with_phase_trigger(self, tmp_path):
        result = plant_seed(tmp_path, "Add caching", trigger="after_phase:auth")
        assert result["trigger"]["type"] == "after_phase"
        assert result["trigger"]["value"] == "auth"

    def test_plant_with_milestone_trigger(self, tmp_path):
        result = plant_seed(tmp_path, "Optimize queries", trigger="after_milestone:v1.0")
        assert result["trigger"]["type"] == "after_milestone"
        assert result["trigger"]["value"] == "v1.0"

    def test_plant_creates_file(self, tmp_path):
        plant_seed(tmp_path, "Test idea")
        backlog_file = tmp_path / ".meridian" / "backlog.md"
        assert backlog_file.exists()
        content = backlog_file.read_text()
        assert "[SEED-001]" in content
        assert "Test idea" in content

    def test_plant_multiple(self, tmp_path):
        plant_seed(tmp_path, "First idea")
        result = plant_seed(tmp_path, "Second idea")
        assert result["id"] == "SEED-002"
        seeds = list_seeds(tmp_path)
        assert len(seeds) == 2

    def test_plant_invalid_trigger(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid trigger type"):
            plant_seed(tmp_path, "Bad trigger", trigger="bogus:foo")

    def test_plant_creates_meridian_dir(self, tmp_path):
        plant_seed(tmp_path, "test")
        assert (tmp_path / ".meridian").is_dir()


# ── List Tests ───────────────────────────────────────────────────────────────


class TestListSeeds:
    def test_empty_dir(self, tmp_path):
        assert list_seeds(tmp_path) == []

    def test_lists_all_seeds(self, tmp_path):
        plant_seed(tmp_path, "Alpha")
        plant_seed(tmp_path, "Beta")
        plant_seed(tmp_path, "Gamma")
        seeds = list_seeds(tmp_path)
        assert len(seeds) == 3
        assert seeds[0]["id"] == "SEED-001"
        assert seeds[2]["id"] == "SEED-003"

    def test_returns_expected_keys(self, tmp_path):
        plant_seed(tmp_path, "Test", trigger="after_phase:auth")
        seeds = list_seeds(tmp_path)
        seed = seeds[0]
        assert "id" in seed
        assert "idea" in seed
        assert "status" in seed
        assert "trigger" in seed
        assert "created" in seed
        assert seed["status"] == "active"
        assert seed["trigger"]["type"] == "after_phase"


# ── Promote Tests ────────────────────────────────────────────────────────────


class TestPromoteSeed:
    def test_promote_active_seed(self, tmp_path):
        plant_seed(tmp_path, "Good idea")
        result = promote_seed(tmp_path, "SEED-001")
        assert result["new_status"] == "promoted"
        seeds = list_seeds(tmp_path)
        assert seeds[0]["status"] == "promoted"

    def test_promote_nonexistent(self, tmp_path):
        plant_seed(tmp_path, "Test")
        with pytest.raises(ValueError, match="not found"):
            promote_seed(tmp_path, "SEED-999")

    def test_promote_already_promoted(self, tmp_path):
        plant_seed(tmp_path, "Test")
        promote_seed(tmp_path, "SEED-001")
        with pytest.raises(ValueError, match="can only promote active"):
            promote_seed(tmp_path, "SEED-001")

    def test_promote_no_backlog(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            promote_seed(tmp_path, "SEED-001")


# ── Dismiss Tests ────────────────────────────────────────────────────────────


class TestDismissSeed:
    def test_dismiss_active_seed(self, tmp_path):
        plant_seed(tmp_path, "Bad idea")
        result = dismiss_seed(tmp_path, "SEED-001")
        assert result["new_status"] == "dismissed"
        seeds = list_seeds(tmp_path)
        assert seeds[0]["status"] == "dismissed"

    def test_dismiss_nonexistent(self, tmp_path):
        plant_seed(tmp_path, "Test")
        with pytest.raises(ValueError, match="not found"):
            dismiss_seed(tmp_path, "SEED-999")

    def test_dismiss_already_dismissed(self, tmp_path):
        plant_seed(tmp_path, "Test")
        dismiss_seed(tmp_path, "SEED-001")
        with pytest.raises(ValueError, match="can only dismiss active"):
            dismiss_seed(tmp_path, "SEED-001")


# ── Trigger Tests ────────────────────────────────────────────────────────────


class TestCheckTriggers:
    def test_no_triggers_met(self, tmp_path):
        plant_seed(tmp_path, "Idea A", trigger="after_phase:auth")
        triggered = check_triggers(tmp_path, completed_phases=["other"])
        assert len(triggered) == 0

    def test_phase_trigger_met(self, tmp_path):
        plant_seed(tmp_path, "Idea A", trigger="after_phase:auth")
        triggered = check_triggers(tmp_path, completed_phases=["auth"])
        assert len(triggered) == 1
        assert triggered[0]["idea"] == "Idea A"

    def test_milestone_trigger_met(self, tmp_path):
        plant_seed(tmp_path, "Idea B", trigger="after_milestone:v1.0")
        triggered = check_triggers(tmp_path, completed_milestones=["v1.0"])
        assert len(triggered) == 1
        assert triggered[0]["idea"] == "Idea B"

    def test_manual_never_auto_triggers(self, tmp_path):
        plant_seed(tmp_path, "Manual idea", trigger="manual")
        triggered = check_triggers(tmp_path, completed_phases=["all"], completed_milestones=["all"])
        assert len(triggered) == 0

    def test_dismissed_seeds_not_triggered(self, tmp_path):
        plant_seed(tmp_path, "Old idea", trigger="after_phase:auth")
        dismiss_seed(tmp_path, "SEED-001")
        triggered = check_triggers(tmp_path, completed_phases=["auth"])
        assert len(triggered) == 0

    def test_promoted_seeds_not_triggered(self, tmp_path):
        plant_seed(tmp_path, "Done idea", trigger="after_phase:auth")
        promote_seed(tmp_path, "SEED-001")
        triggered = check_triggers(tmp_path, completed_phases=["auth"])
        assert len(triggered) == 0

    def test_empty_backlog(self, tmp_path):
        triggered = check_triggers(tmp_path)
        assert triggered == []
