#!/usr/bin/env python3
"""Tests for Meridian phase manipulation."""

import pytest

from scripts.phase_manipulation import (
    insert_phase,
    list_phases_ordered,
    remove_phase,
    renumber_phases,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
)


def _ms(db):
    create_project(db, name="Test", repo_path="/tmp/test")
    ms = create_milestone(db, "v1", "V1", project_id="default")
    transition_milestone(db, ms["id"], "active")
    return ms


class TestInsertPhase:
    def test_insert_between(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "Phase 1", "first", sequence=1)
        create_phase(db, ms["id"], "Phase 2", "second", sequence=2)

        new = insert_phase(db, ms["id"], 1, "Urgent Fix", "hotfix")
        assert 1 < new["sequence"] < 2

    def test_insert_at_end(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "Phase 1", "first", sequence=1)

        new = insert_phase(db, ms["id"], 1, "Phase 2", "second")
        assert new["sequence"] == 2.0

    def test_insert_with_criteria(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "Phase 1", "first", sequence=1)

        new = insert_phase(
            db, ms["id"], 1, "Phase 1.5", "mid",
            acceptance_criteria=["Test passes"],
        )
        assert new["name"] == "Phase 1.5"


class TestRemovePhase:
    def test_remove_planned_phase(self, db):
        ms = _ms(db)
        p1 = create_phase(db, ms["id"], "Keep", "desc", sequence=1)
        p2 = create_phase(db, ms["id"], "Remove", "desc", sequence=2)
        p3 = create_phase(db, ms["id"], "Also Keep", "desc", sequence=3)

        result = remove_phase(db, p2["id"])
        assert result["removed"]["name"] == "Remove"

        remaining = list_phases_ordered(db, ms["id"])
        names = [p["name"] for p in remaining]
        assert "Remove" not in names
        assert len(remaining) == 2

    def test_remove_with_plans(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "With Plans", "desc", sequence=1)
        create_plan(db, p["id"], "Plan A", "do stuff")
        create_plan(db, p["id"], "Plan B", "more stuff")

        result = remove_phase(db, p["id"])
        assert "2" in result["message"]  # 2 plans deleted

    def test_cannot_remove_non_planned(self, db):
        from scripts.state import transition_phase
        ms = _ms(db)
        p = create_phase(db, ms["id"], "Active", "desc")
        transition_phase(db, p["id"], "context_gathered")

        with pytest.raises(ValueError, match="must be 'planned'"):
            remove_phase(db, p["id"])

    def test_remove_nonexistent(self, db):
        _ms(db)
        with pytest.raises(ValueError, match="not found"):
            remove_phase(db, 999)


class TestRenumberPhases:
    def test_renumber_after_gap(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "A", "desc", sequence=1)
        create_phase(db, ms["id"], "B", "desc", sequence=3)
        create_phase(db, ms["id"], "C", "desc", sequence=5)

        results = renumber_phases(db, ms["id"])
        seqs = [r["new_sequence"] for r in results]
        assert seqs == [1, 2, 3]

    def test_renumber_decimal_sequences(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "A", "desc", sequence=1)
        create_phase(db, ms["id"], "B", "desc", sequence=3)
        insert_phase(db, ms["id"], 1, "A.5", "mid")  # gets sequence 2.0

        results = renumber_phases(db, ms["id"])
        seqs = [r["new_sequence"] for r in results]
        assert seqs == [1, 2, 3]


class TestListPhasesOrdered:
    def test_decimal_ordering(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "B", "desc", sequence=2)
        create_phase(db, ms["id"], "A", "desc", sequence=1)
        insert_phase(db, ms["id"], 1, "A.5", "mid")

        ordered = list_phases_ordered(db, ms["id"])
        names = [p["name"] for p in ordered]
        assert names == ["A", "A.5", "B"]
