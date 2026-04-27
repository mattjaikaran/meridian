"""Tests for the Meridian spike workflow."""

import pytest

from scripts.spikes import (
    _sanitize_slug,
    add_finding,
    check_spike_gate,
    close_spike,
    create_spike,
    frontier_scan,
    get_spike,
    list_spikes,
    wrap_up_spike,
)
from scripts.state import create_milestone, create_phase, create_project, transition_milestone


# ── Slug sanitization ─────────────────────────────────────────────────────────


class TestSanitizeSlug:
    def test_simple(self):
        assert _sanitize_slug("Auth spike") == "auth-spike"

    def test_special_chars(self):
        assert _sanitize_slug("Fix bug #42!") == "fix-bug-42"

    def test_truncated(self):
        result = _sanitize_slug("a" * 80)
        assert len(result) <= 60

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Cannot derive"):
            _sanitize_slug("!!!")


# ── Create ────────────────────────────────────────────────────────────────────


class TestCreateSpike:
    def test_creates_open_spike(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        s = create_spike(db, "Auth exploration", "How should auth work?", tmp_path)
        assert s["slug"] == "auth-exploration"
        assert s["status"] == "open"
        assert s["question"] == "How should auth work?"

    def test_writes_manifest(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "DB design", "Which DB fits best?", tmp_path)
        manifest = tmp_path / ".planning" / "spikes" / "db-design" / "MANIFEST.md"
        assert manifest.exists()
        text = manifest.read_text()
        assert "DB design" in text
        assert "Which DB fits best?" in text

    def test_creates_findings_dir(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Cache spike", "Redis or Memcached?", tmp_path)
        findings = tmp_path / ".planning" / "spikes" / "cache-spike" / "findings"
        assert findings.is_dir()

    def test_explicit_slug(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        s = create_spike(db, "Title", "Q?", tmp_path, slug="custom-slug")
        assert s["slug"] == "custom-slug"

    def test_duplicate_slug_raises(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Auth exploration", "Q?", tmp_path)
        with pytest.raises(Exception):
            create_spike(db, "Auth exploration", "Q2?", tmp_path)

    def test_with_phase_id(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_milestone(db, milestone_id="v1", name="V1", project_id="default")
        transition_milestone(db, "v1", "active")
        ph = create_phase(db, milestone_id="v1", name="Feature", description="desc")
        s = create_spike(db, "Feature spike", "Q?", tmp_path, phase_id=ph["id"])
        assert s["phase_id"] == ph["id"]


# ── Get ───────────────────────────────────────────────────────────────────────


class TestGetSpike:
    def test_returns_none_missing(self, db):
        assert get_spike(db, "nonexistent") is None

    def test_returns_spike(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "My spike", "Q?", tmp_path)
        s = get_spike(db, "my-spike")
        assert s is not None
        assert s["title"] == "My spike"


# ── List ──────────────────────────────────────────────────────────────────────


class TestListSpikes:
    def test_empty(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        assert list_spikes(db) == []

    def test_lists_all(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Spike one", "Q1?", tmp_path)
        create_spike(db, "Spike two", "Q2?", tmp_path)
        assert len(list_spikes(db)) == 2

    def test_filter_open(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Open spike", "Q?", tmp_path)
        s2 = create_spike(db, "Closed spike", "Q?", tmp_path)
        close_spike(db, s2["slug"], "done", tmp_path)
        result = list_spikes(db, status="open")
        assert len(result) == 1
        assert result[0]["slug"] == "open-spike"

    def test_filter_closed(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Keep open", "Q?", tmp_path)
        s2 = create_spike(db, "Will close", "Q?", tmp_path)
        close_spike(db, s2["slug"], "done", tmp_path)
        result = list_spikes(db, status="closed")
        assert len(result) == 1
        assert result[0]["slug"] == "will-close"

    def test_invalid_status_raises(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        with pytest.raises(ValueError, match="Invalid status filter"):
            list_spikes(db, status="invalid")

    def test_newest_first(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Older spike", "Q?", tmp_path)
        create_spike(db, "Newer spike", "Q?", tmp_path)
        result = list_spikes(db)
        assert result[0]["slug"] == "newer-spike"


# ── Add finding ───────────────────────────────────────────────────────────────


class TestAddFinding:
    def test_writes_file(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "My spike", "Q?", tmp_path)
        path = add_finding("my-spike", "research.md", "# Notes\nStuff found.", tmp_path)
        assert path.exists()
        assert "Notes" in path.read_text()

    def test_creates_findings_dir(self, tmp_path):
        add_finding("no-spike", "note.md", "content", tmp_path)
        assert (tmp_path / ".planning" / "spikes" / "no-spike" / "findings" / "note.md").exists()


# ── Close ─────────────────────────────────────────────────────────────────────


class TestCloseSpike:
    def test_closes_open_spike(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "To close", "Q?", tmp_path)
        s = close_spike(db, "to-close", "Answer: yes", tmp_path)
        assert s["status"] == "closed"
        assert s["outcome"] == "Answer: yes"
        assert s["closed_at"] is not None

    def test_updates_manifest(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Manifest test", "Q?", tmp_path)
        close_spike(db, "manifest-test", "Found it.", tmp_path)
        text = (tmp_path / ".planning" / "spikes" / "manifest-test" / "MANIFEST.md").read_text()
        assert "Found it." in text
        assert "closed" in text

    def test_close_nonexistent_raises(self, db, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            close_spike(db, "ghost", "outcome", tmp_path)

    def test_close_already_closed_raises(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Double close", "Q?", tmp_path)
        close_spike(db, "double-close", "done", tmp_path)
        with pytest.raises(ValueError, match="already closed"):
            close_spike(db, "double-close", "again", tmp_path)


# ── Wrap-up ───────────────────────────────────────────────────────────────────


class TestWrapUpSpike:
    def test_closes_and_records_learnings(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Learn spike", "Q?", tmp_path)
        result = wrap_up_spike(
            db,
            "learn-spike",
            "Outcome: use Redis.",
            ["Always set TTL on cache keys", "Use connection pooling"],
            tmp_path,
        )
        assert result["spike"]["status"] == "closed"
        assert len(result["learning_ids"]) == 2

    def test_no_learnings(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Empty learnings", "Q?", tmp_path)
        result = wrap_up_spike(db, "empty-learnings", "done", [], tmp_path)
        assert result["spike"]["status"] == "closed"
        assert result["learning_ids"] == []

    def test_learnings_linked_to_phase(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_milestone(db, milestone_id="v1", name="V1", project_id="default")
        transition_milestone(db, "v1", "active")
        ph = create_phase(db, milestone_id="v1", name="Feat", description="d")
        create_spike(db, "Phase spike", "Q?", tmp_path, phase_id=ph["id"])
        result = wrap_up_spike(db, "phase-spike", "outcome", ["rule one"], tmp_path)
        # Learning should exist in DB linked to phase
        row = db.execute(
            "SELECT * FROM learning WHERE id = ?", (result["learning_ids"][0],)
        ).fetchone()
        assert row["phase_id"] == ph["id"]
        assert row["rule"] == "rule one"


# ── Frontier scan ─────────────────────────────────────────────────────────────


class TestFrontierScan:
    def test_empty_project(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        result = frontier_scan(db, tmp_path)
        assert result["open_spikes"] == []
        assert result["closed_spikes"] == []
        assert result["orphaned_dirs"] == []

    def test_separates_open_closed(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_spike(db, "Open one", "Q?", tmp_path)
        s2 = create_spike(db, "Closed one", "Q?", tmp_path)
        close_spike(db, s2["slug"], "done", tmp_path)
        result = frontier_scan(db, tmp_path)
        assert len(result["open_spikes"]) == 1
        assert len(result["closed_spikes"]) == 1

    def test_detects_orphaned_dirs(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        orphan = tmp_path / ".planning" / "spikes" / "orphan-spike"
        orphan.mkdir(parents=True)
        result = frontier_scan(db, tmp_path)
        assert "orphan-spike" in result["orphaned_dirs"]

    def test_proposes_unspike_phases(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_milestone(db, milestone_id="v1", name="V1", project_id="default")
        transition_milestone(db, "v1", "active")
        create_phase(db, milestone_id="v1", name="Needs spike", description="d")
        result = frontier_scan(db, tmp_path)
        assert len(result["proposals"]) >= 1
        assert "Needs spike" in result["proposals"][0]["suggested_title"]


# ── Gate check ────────────────────────────────────────────────────────────────


class TestCheckSpikeGate:
    def test_no_blockers(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_milestone(db, milestone_id="v1", name="V1", project_id="default")
        transition_milestone(db, "v1", "active")
        ph = create_phase(db, milestone_id="v1", name="Clean phase", description="d")
        assert check_spike_gate(db, ph["id"]) == []

    def test_open_spike_blocks(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_milestone(db, milestone_id="v1", name="V1", project_id="default")
        transition_milestone(db, "v1", "active")
        ph = create_phase(db, milestone_id="v1", name="Blocked phase", description="d")
        create_spike(db, "Blocking spike", "Q?", tmp_path, phase_id=ph["id"])
        blockers = check_spike_gate(db, ph["id"])
        assert len(blockers) == 1
        assert blockers[0]["slug"] == "blocking-spike"

    def test_closed_spike_not_blocking(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_milestone(db, milestone_id="v1", name="V1", project_id="default")
        transition_milestone(db, "v1", "active")
        ph = create_phase(db, milestone_id="v1", name="Clear phase", description="d")
        create_spike(db, "Done spike", "Q?", tmp_path, phase_id=ph["id"])
        close_spike(db, "done-spike", "outcome", tmp_path)
        assert check_spike_gate(db, ph["id"]) == []
