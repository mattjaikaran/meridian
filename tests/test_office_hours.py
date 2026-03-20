#!/usr/bin/env python3
"""Tests for office hours mode in /meridian:plan --deep."""

from pathlib import Path


PLAN_SKILL_PATH = Path(__file__).parent.parent / "skills" / "plan" / "SKILL.md"

REQUIRED_QUESTIONS = [
    "Who needs this",
    "What's the status quo",
    "What's the narrowest wedge",
    "What breaks without it",
    "What does success look like",
]


class TestOfficeHoursQuestions:
    def test_skill_file_exists(self):
        assert PLAN_SKILL_PATH.exists()

    def test_deep_flag_documented(self):
        content = PLAN_SKILL_PATH.read_text()
        assert "--deep" in content

    def test_all_five_questions_present(self):
        content = PLAN_SKILL_PATH.read_text()
        for question in REQUIRED_QUESTIONS:
            assert question in content, f"Missing question: {question}"

    def test_office_hours_step_exists(self):
        content = PLAN_SKILL_PATH.read_text()
        assert "Office Hours" in content
        assert "Step 3.5" in content

    def test_constraint_category_used(self):
        """Office hours answers should be stored as constraint decisions."""
        content = PLAN_SKILL_PATH.read_text()
        assert "category='constraint'" in content

    def test_answers_feed_into_brainstorm(self):
        content = PLAN_SKILL_PATH.read_text()
        assert "narrowest wedge" in content.lower()
        assert "acceptance criteria" in content.lower()

    def test_questions_ordered(self):
        """Questions should appear in order: who, status quo, wedge, breaks, success."""
        content = PLAN_SKILL_PATH.read_text()
        positions = []
        for q in REQUIRED_QUESTIONS:
            pos = content.find(q)
            assert pos >= 0, f"Question not found: {q}"
            positions.append(pos)
        assert positions == sorted(positions), "Questions are out of order"

    def test_ask_user_question_mentioned(self):
        content = PLAN_SKILL_PATH.read_text()
        assert "AskUserQuestion" in content
