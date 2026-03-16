"""Tests for roadmap_sync module -- pure text transformation functions."""

from scripts.roadmap_sync import (
    sync_roadmap_plan_checkbox,
    sync_roadmap_phase_checkbox,
    sync_roadmap_progress_table,
    sync_requirements_status,
)

# ---------------------------------------------------------------------------
# Sample markdown fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROADMAP = """\
# Roadmap: Meridian

## Milestones

### v1.1 Polish & Reliability

- [x] **Phase 5: Lint Cleanup** - Fix all E501 violations
- [ ] **Phase 6: Nyquist Compliance** - Fill validation gaps
- [ ] **Phase 7: Roadmap Automation** - Auto-sync ROADMAP.md

## Phase Details

### Phase 5: Lint Cleanup
Plans:
- [x] 05-01-PLAN.md — Fix all E501 line-length violations

### Phase 6: Nyquist Compliance
Plans:
- [x] 06-01-PLAN.md — Build Nyquist validation engine
- [ ] 06-02-PLAN.md — Retroactive gap fill and verify-phase skill

### Phase 7: Roadmap Automation
Plans:
- [ ] 07-01-PLAN.md — Build and test roadmap_sync.py with TDD
- [ ] 07-02-PLAN.md — Wire sync hooks into state.py

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 5. Lint Cleanup | v1.1 | 1/1 | Complete | 2026-03-14 |
| 6. Nyquist Compliance | v1.1 | 0/2 | Not started | - |
| 7. Roadmap Automation | v1.1 | 0/2 | Not started | - |
"""

SAMPLE_REQUIREMENTS = """\
## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ROAD-01 | Phase 7 | Pending |
| ROAD-02 | Phase 7 | Pending |
| COMP-01 | Phase 6 | Complete |
| QUAL-01 | Phase 5 | Complete |
"""


# ---------------------------------------------------------------------------
# sync_roadmap_plan_checkbox
# ---------------------------------------------------------------------------

class TestSyncRoadmapPlanCheckbox:
    """Tests for plan checkbox toggling."""

    def test_mark_complete(self):
        result = sync_roadmap_plan_checkbox(
            SAMPLE_ROADMAP, "07-01-PLAN.md", True,
        )
        assert "- [x] 07-01-PLAN.md" in result
        # Other plan lines unchanged
        assert "- [ ] 07-02-PLAN.md" in result

    def test_mark_incomplete(self):
        result = sync_roadmap_plan_checkbox(
            SAMPLE_ROADMAP, "06-01-PLAN.md", False,
        )
        assert "- [ ] 06-01-PLAN.md" in result

    def test_idempotent_already_checked(self):
        result = sync_roadmap_plan_checkbox(
            SAMPLE_ROADMAP, "05-01-PLAN.md", True,
        )
        assert "- [x] 05-01-PLAN.md" in result
        assert result == SAMPLE_ROADMAP  # no change

    def test_idempotent_already_unchecked(self):
        result = sync_roadmap_plan_checkbox(
            SAMPLE_ROADMAP, "07-01-PLAN.md", False,
        )
        assert "- [ ] 07-01-PLAN.md" in result
        assert result == SAMPLE_ROADMAP  # no change

    def test_missing_slug_returns_unchanged(self):
        result = sync_roadmap_plan_checkbox(
            SAMPLE_ROADMAP, "99-01-PLAN.md", True,
        )
        assert result == SAMPLE_ROADMAP

    def test_empty_text(self):
        result = sync_roadmap_plan_checkbox("", "07-01-PLAN.md", True)
        assert result == ""


# ---------------------------------------------------------------------------
# sync_roadmap_phase_checkbox
# ---------------------------------------------------------------------------

class TestSyncRoadmapPhaseCheckbox:
    """Tests for phase checkbox toggling in milestone section."""

    def test_mark_complete(self):
        result = sync_roadmap_phase_checkbox(SAMPLE_ROADMAP, 7, True)
        assert "- [x] **Phase 7:" in result

    def test_mark_incomplete(self):
        result = sync_roadmap_phase_checkbox(SAMPLE_ROADMAP, 5, False)
        assert "- [ ] **Phase 5:" in result

    def test_idempotent_already_checked(self):
        result = sync_roadmap_phase_checkbox(SAMPLE_ROADMAP, 5, True)
        assert "- [x] **Phase 5:" in result
        assert result == SAMPLE_ROADMAP

    def test_idempotent_already_unchecked(self):
        result = sync_roadmap_phase_checkbox(SAMPLE_ROADMAP, 6, False)
        assert "- [ ] **Phase 6:" in result
        assert result == SAMPLE_ROADMAP

    def test_missing_phase_returns_unchanged(self):
        result = sync_roadmap_phase_checkbox(SAMPLE_ROADMAP, 99, True)
        assert result == SAMPLE_ROADMAP

    def test_empty_text(self):
        result = sync_roadmap_phase_checkbox("", 7, True)
        assert result == ""


# ---------------------------------------------------------------------------
# sync_roadmap_progress_table
# ---------------------------------------------------------------------------

class TestSyncRoadmapProgressTable:
    """Tests for progress table row updates."""

    def test_update_status_and_date(self):
        result = sync_roadmap_progress_table(
            SAMPLE_ROADMAP, 7, "In progress", None,
        )
        # Row should have updated status
        assert "In progress" in result
        # Date should be "-" when None
        for line in result.splitlines():
            if "7. Roadmap Automation" in line:
                assert "In progress" in line
                assert line.strip().endswith("- |")
                break
        else:
            raise AssertionError("Phase 7 row not found")

    def test_update_with_date(self):
        result = sync_roadmap_progress_table(
            SAMPLE_ROADMAP, 7, "Complete", "2026-03-16",
        )
        for line in result.splitlines():
            if "7. Roadmap Automation" in line:
                assert "Complete" in line
                assert "2026-03-16" in line
                break
        else:
            raise AssertionError("Phase 7 row not found")

    def test_missing_phase_returns_unchanged(self):
        result = sync_roadmap_progress_table(
            SAMPLE_ROADMAP, 99, "Complete", "2026-03-16",
        )
        assert result == SAMPLE_ROADMAP

    def test_empty_text(self):
        result = sync_roadmap_progress_table("", 7, "Complete", None)
        assert result == ""


# ---------------------------------------------------------------------------
# sync_requirements_status
# ---------------------------------------------------------------------------

class TestSyncRequirementsStatus:
    """Tests for requirements traceability table updates."""

    def test_update_pending_to_complete(self):
        result = sync_requirements_status(
            SAMPLE_REQUIREMENTS, "ROAD-01", "Complete",
        )
        for line in result.splitlines():
            if "ROAD-01" in line:
                assert "Complete" in line
                assert "Pending" not in line
                break
        else:
            raise AssertionError("ROAD-01 row not found")

    def test_idempotent_already_correct(self):
        result = sync_requirements_status(
            SAMPLE_REQUIREMENTS, "COMP-01", "Complete",
        )
        assert result == SAMPLE_REQUIREMENTS

    def test_missing_req_returns_unchanged(self):
        result = sync_requirements_status(
            SAMPLE_REQUIREMENTS, "FAKE-99", "Complete",
        )
        assert result == SAMPLE_REQUIREMENTS

    def test_empty_text(self):
        result = sync_requirements_status("", "ROAD-01", "Complete")
        assert result == ""

    def test_only_target_row_updated(self):
        result = sync_requirements_status(
            SAMPLE_REQUIREMENTS, "ROAD-01", "Complete",
        )
        # ROAD-02 should still be Pending
        for line in result.splitlines():
            if "ROAD-02" in line:
                assert "Pending" in line
                break
