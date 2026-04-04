#!/usr/bin/env python3
"""Tests for Meridian discuss phase module."""

import json

import pytest

from scripts.discuss_phase import (
    apply_answers,
    generate_context_doc,
    generate_questions,
    identify_gray_areas,
    run_discuss,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    list_decisions,
    transition_milestone,
)


class TestIdentifyGrayAreas:
    def test_detects_architecture_keywords(self):
        areas = identify_gray_areas(
            "Auth Service",
            "Build a new authentication service with endpoints",
            ["Users can log in via API endpoint"],
            [],
        )
        topics = [a["category"] for a in areas]
        assert "architecture" in topics

    def test_detects_data_model_keywords(self):
        areas = identify_gray_areas(
            "Schema Migration",
            "Create database schema for user storage",
            ["Persist user data in tables"],
            [],
        )
        topics = [a["category"] for a in areas]
        assert "data_model" in topics

    def test_detects_api_keywords(self):
        areas = identify_gray_areas(
            "REST API",
            "Build REST endpoints for resource management",
            ["Expose REST API for CRUD"],
            [],
        )
        topics = [a["category"] for a in areas]
        assert "api_design" in topics

    def test_detects_testing_keywords(self):
        areas = identify_gray_areas(
            "Test Suite",
            "Add integration test coverage for auth",
            ["All integration tests pass"],
            [],
        )
        topics = [a["category"] for a in areas]
        assert "testing_strategy" in topics

    def test_detects_integration_keywords(self):
        areas = identify_gray_areas(
            "Webhook Sync",
            "Sync data with external webhook provider",
            ["External sync works"],
            [],
        )
        topics = [a["category"] for a in areas]
        assert "integration" in topics

    def test_detects_performance_keywords(self):
        areas = identify_gray_areas(
            "Batch Processing",
            "Implement batch processing with caching for scale",
            ["Handles concurrent batch operations"],
            [],
        )
        topics = [a["category"] for a in areas]
        assert "performance" in topics

    def test_filters_prior_decisions(self):
        prior = [{"summary": "architecture approach for auth service"}]
        areas = identify_gray_areas(
            "Auth Service",
            "Build a new authentication service with endpoints",
            [],
            prior,
        )
        arch_areas = [a for a in areas if a["category"] == "architecture"]
        assert len(arch_areas) == 0

    def test_no_keywords_returns_empty(self):
        areas = identify_gray_areas(
            "Simple Fix",
            "Fix a typo in the readme",
            ["Typo is fixed"],
            [],
        )
        assert areas == []

    def test_gray_area_structure(self):
        areas = identify_gray_areas(
            "API Module",
            "Build API endpoint handler",
            [],
            [],
        )
        for area in areas:
            assert "topic" in area
            assert "options" in area
            assert "recommendation" in area
            assert "context" in area
            assert "category" in area
            assert isinstance(area["options"], list)
            for opt in area["options"]:
                assert "name" in opt
                assert "description" in opt

    def test_multiple_categories_detected(self):
        areas = identify_gray_areas(
            "Full Stack Feature",
            "Build API endpoint with database schema and integration tests",
            ["API endpoint works", "Database stores data", "Tests pass"],
            [],
        )
        categories = {a["category"] for a in areas}
        assert len(categories) >= 2


class TestGenerateQuestions:
    def test_interactive_mode(self):
        areas = [
            {
                "topic": "Architecture",
                "options": [{"name": "A"}, {"name": "B"}],
                "recommendation": "A",
                "context": "Some context",
                "category": "architecture",
            }
        ]
        questions = generate_questions(areas, mode="interactive")
        assert len(questions) == 2  # primary + secondary
        assert questions[0]["options"] == ["A", "B"]
        assert questions[0]["default"] == "A"

    def test_batch_mode(self):
        areas = [
            {
                "topic": "Architecture",
                "options": [{"name": "A"}, {"name": "B"}],
                "recommendation": "A",
                "context": "ctx",
                "category": "architecture",
            }
        ]
        questions = generate_questions(areas, mode="batch")
        assert len(questions) == 1  # no secondary in batch

    def test_auto_mode_includes_answer(self):
        areas = [
            {
                "topic": "Architecture",
                "options": [{"name": "A"}, {"name": "B"}],
                "recommendation": "A",
                "context": "ctx",
                "category": "architecture",
            }
        ]
        questions = generate_questions(areas, mode="auto")
        assert questions[0]["answer"] == "A"

    def test_empty_areas(self):
        questions = generate_questions([], mode="interactive")
        assert questions == []

    def test_question_structure(self):
        areas = [
            {
                "topic": "Test",
                "options": [{"name": "X"}],
                "recommendation": "X",
                "context": "",
                "category": "testing_strategy",
            }
        ]
        questions = generate_questions(areas)
        for q in questions:
            assert "area_index" in q
            assert "question" in q
            assert "options" in q
            assert "default" in q


class TestApplyAnswers:
    def test_persists_decisions(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Test Phase", "Build API service")

        gray_areas = [
            {
                "topic": "Arch for Test Phase",
                "options": [{"name": "A", "description": "opt A"}],
                "recommendation": "A",
                "context": "ctx",
                "category": "architecture",
            }
        ]
        answers = [{"area_index": 0, "answer": "A"}]

        result = apply_answers(
            db, phase["id"], "default", gray_areas, answers, tmp_path
        )

        assert len(result["decisions"]) == 1
        assert "context_doc" in result

        # Verify persisted in DB
        decisions = list_decisions(db, project_id="default", phase_id=phase["id"])
        assert len(decisions) >= 1

    def test_skips_out_of_range(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Test Phase", "desc")

        gray_areas = [{"topic": "T", "options": [], "recommendation": "", "context": "", "category": "architecture"}]
        answers = [{"area_index": 5, "answer": "X"}]

        result = apply_answers(
            db, phase["id"], "default", gray_areas, answers, tmp_path
        )
        assert len(result["decisions"]) == 0

    def test_logs_discussion(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Test Phase", "Build module")

        gray_areas = [
            {
                "topic": "Approach",
                "options": [{"name": "A", "description": "opt"}],
                "recommendation": "A",
                "context": "why",
                "category": "approach",
            }
        ]
        answers = [{"area_index": 0, "answer": "A"}]

        apply_answers(db, phase["id"], "default", gray_areas, answers, tmp_path)

        log_file = tmp_path / ".meridian" / "DISCUSSION-LOG.md"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Approach" in content


class TestGenerateContextDoc:
    def test_basic_structure(self):
        phase = {"name": "Test Phase", "description": "Build something"}
        decisions = [
            {"decision_id": "DEC-001", "summary": "Use REST", "rationale": "Standard", "category": "api_design"}
        ]
        doc = generate_context_doc(phase, decisions)
        assert "## Domain" in doc
        assert "## Decisions" in doc
        assert "## Code Context" in doc
        assert "## Deferred" in doc
        assert "DEC-001" in doc
        assert "Use REST" in doc

    def test_with_acceptance_criteria(self):
        phase = {
            "name": "Test",
            "description": "desc",
            "acceptance_criteria": json.dumps(["Criterion 1", "Criterion 2"]),
        }
        doc = generate_context_doc(phase, [])
        assert "Criterion 1" in doc
        assert "Criterion 2" in doc

    def test_with_prior_context(self):
        doc = generate_context_doc(
            {"name": "T", "description": "d"},
            [],
            prior_context="Existing patterns found",
        )
        assert "Existing patterns found" in doc

    def test_empty_decisions(self):
        doc = generate_context_doc({"name": "T", "description": "d"}, [])
        assert "No decisions recorded yet" in doc

    def test_deferred_items(self):
        decisions = [
            {"decision_id": "DEC-001", "summary": "Defer caching", "rationale": "", "category": "deferred"}
        ]
        doc = generate_context_doc({"name": "T", "description": "d"}, decisions)
        assert "Defer caching" in doc


class TestRunDiscuss:
    def test_auto_mode_applies_answers(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(
            db, ms["id"], "API Service", "Build API service with endpoints"
        )

        result = run_discuss(
            db, phase["id"], "default", tmp_path, mode="auto"
        )

        assert result["mode"] == "auto"
        assert result["context_doc"] is not None
        assert len(result["gray_areas"]) > 0

    def test_interactive_mode_returns_questions(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(
            db, ms["id"], "DB Schema", "Create database schema and tables"
        )

        result = run_discuss(
            db, phase["id"], "default", tmp_path, mode="interactive"
        )

        assert result["mode"] == "interactive"
        assert len(result["questions"]) > 0

    def test_phase_not_found(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        result = run_discuss(db, 999, "default", tmp_path)
        assert "error" in result

    def test_chain_flag_passed_through(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Test", "Build something")

        result = run_discuss(
            db, phase["id"], "default", tmp_path, chain=True
        )
        assert result["chain"] is True

    def test_no_gray_areas_still_returns_context(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Simple Fix", "Fix a typo")

        result = run_discuss(
            db, phase["id"], "default", tmp_path, mode="auto"
        )

        assert result["context_doc"] is not None
        assert len(result["gray_areas"]) == 0
