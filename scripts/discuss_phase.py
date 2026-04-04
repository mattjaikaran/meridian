#!/usr/bin/env python3
"""Meridian phase discussion — identify gray areas, generate questions, persist decisions."""

import json
import logging
import sqlite3
from pathlib import Path

from scripts.db import retry_on_busy
from scripts.discussion import log_discussion
from scripts.state import (
    create_decision,
    get_phase,
    list_decisions,
)

logger = logging.getLogger(__name__)

# Categories of gray areas worth discussing before implementation
GRAY_AREA_CATEGORIES: list[str] = [
    "architecture",
    "data_model",
    "api_design",
    "testing_strategy",
    "integration",
    "performance",
]

# Map gray area categories to valid DB decision categories
# DB constraint: architecture, approach, trade_off, tooling, constraint, deviation
_CATEGORY_TO_DB: dict[str, str] = {
    "architecture": "architecture",
    "data_model": "architecture",
    "api_design": "approach",
    "testing_strategy": "approach",
    "integration": "tooling",
    "performance": "trade_off",
}


def identify_gray_areas(
    phase_name: str,
    phase_description: str,
    acceptance_criteria: list[str],
    prior_decisions: list[dict],
) -> list[dict]:
    """Analyze phase scope and return implementation decisions worth discussing.

    Each gray area is a dict with:
        - topic: str — what needs deciding
        - options: list[dict] — each with 'name' and 'description'
        - recommendation: str — suggested default
        - context: str — why this matters
        - category: str — one of GRAY_AREA_CATEGORIES

    Topics already covered by prior_decisions are filtered out.
    """
    prior_topics = {d.get("summary", "").lower() for d in prior_decisions} | {
        d.get("topic", "").lower() for d in prior_decisions
    }

    gray_areas: list[dict] = []
    desc_lower = (phase_description or "").lower()
    criteria_text = " ".join(acceptance_criteria).lower()
    combined = f"{desc_lower} {criteria_text}"

    # Architecture: detect when phase implies structural decisions
    if any(
        kw in combined
        for kw in [
            "service",
            "module",
            "layer",
            "component",
            "api",
            "endpoint",
            "handler",
            "controller",
        ]
    ):
        area = {
            "topic": f"Architecture approach for {phase_name}",
            "options": [
                {
                    "name": "Modular",
                    "description": "Separate modules with clear interfaces",
                },
                {
                    "name": "Monolithic",
                    "description": "Single module with internal organization",
                },
                {
                    "name": "Layered",
                    "description": "Distinct layers (handler, service, repository)",
                },
            ],
            "recommendation": "Modular",
            "context": (
                "Phase involves structural components — choosing an architecture "
                "pattern early prevents rework."
            ),
            "category": "architecture",
        }
        if area["topic"].lower() not in prior_topics:
            gray_areas.append(area)

    # Data model: detect schema or storage concerns
    if any(
        kw in combined
        for kw in [
            "database",
            "schema",
            "model",
            "table",
            "migration",
            "store",
            "persist",
            "storage",
        ]
    ):
        area = {
            "topic": f"Data model strategy for {phase_name}",
            "options": [
                {
                    "name": "Normalized",
                    "description": "Fully normalized relational schema",
                },
                {
                    "name": "Denormalized",
                    "description": "Denormalized for read performance",
                },
                {
                    "name": "Hybrid",
                    "description": "Normalized core with denormalized views",
                },
            ],
            "recommendation": "Normalized",
            "context": (
                "Phase involves data persistence — schema decisions are expensive to change later."
            ),
            "category": "data_model",
        }
        if area["topic"].lower() not in prior_topics:
            gray_areas.append(area)

    # API design: detect when endpoints or interfaces are involved
    if any(kw in combined for kw in ["api", "endpoint", "rest", "graphql", "rpc", "route"]):
        area = {
            "topic": f"API design pattern for {phase_name}",
            "options": [
                {
                    "name": "RESTful",
                    "description": "Resource-oriented REST endpoints",
                },
                {
                    "name": "RPC-style",
                    "description": "Action-oriented function calls",
                },
                {
                    "name": "Hybrid",
                    "description": "REST for CRUD, RPC for operations",
                },
            ],
            "recommendation": "RESTful",
            "context": (
                "Phase exposes interfaces — consistent API patterns improve developer experience."
            ),
            "category": "api_design",
        }
        if area["topic"].lower() not in prior_topics:
            gray_areas.append(area)

    # Testing strategy: detect when test approach matters
    if any(
        kw in combined
        for kw in [
            "test",
            "tdd",
            "coverage",
            "integration",
            "e2e",
            "validation",
            "verify",
        ]
    ):
        area = {
            "topic": f"Testing strategy for {phase_name}",
            "options": [
                {
                    "name": "Unit-first",
                    "description": "Unit tests with mocked dependencies",
                },
                {
                    "name": "Integration-first",
                    "description": "Integration tests hitting real services",
                },
                {
                    "name": "TDD",
                    "description": "Red-green-refactor cycle",
                },
            ],
            "recommendation": "Integration-first",
            "context": (
                "Phase involves testable behavior — choosing a test strategy "
                "upfront guides implementation."
            ),
            "category": "testing_strategy",
        }
        if area["topic"].lower() not in prior_topics:
            gray_areas.append(area)

    # Integration: detect external system concerns
    if any(
        kw in combined
        for kw in [
            "external",
            "third-party",
            "webhook",
            "sync",
            "import",
            "export",
            "provider",
        ]
    ):
        area = {
            "topic": f"Integration approach for {phase_name}",
            "options": [
                {
                    "name": "Direct",
                    "description": "Direct calls to external systems",
                },
                {
                    "name": "Adapter",
                    "description": "Adapter pattern with swappable backends",
                },
                {
                    "name": "Queue-based",
                    "description": "Async queue for external calls",
                },
            ],
            "recommendation": "Adapter",
            "context": (
                "Phase involves external integrations — isolation patterns "
                "improve testability and resilience."
            ),
            "category": "integration",
        }
        if area["topic"].lower() not in prior_topics:
            gray_areas.append(area)

    # Performance: detect when scale or speed matters
    if any(
        kw in combined
        for kw in [
            "performance",
            "cache",
            "batch",
            "bulk",
            "optimize",
            "scale",
            "concurrent",
            "parallel",
        ]
    ):
        area = {
            "topic": f"Performance strategy for {phase_name}",
            "options": [
                {
                    "name": "Optimize later",
                    "description": "Correct first, optimize when measured",
                },
                {
                    "name": "Cache-first",
                    "description": "Build caching into the design",
                },
                {
                    "name": "Batch-oriented",
                    "description": "Batch operations for throughput",
                },
            ],
            "recommendation": "Optimize later",
            "context": (
                "Phase mentions performance concerns — deciding when to "
                "optimize prevents premature complexity."
            ),
            "category": "performance",
        }
        if area["topic"].lower() not in prior_topics:
            gray_areas.append(area)

    return gray_areas


def generate_questions(
    gray_areas: list[dict],
    mode: str = "interactive",
) -> list[dict]:
    """Produce focused questions for each gray area.

    Args:
        gray_areas: List of gray area dicts from identify_gray_areas().
        mode: One of 'interactive', 'batch', or 'auto'.
            - interactive: 1-2 questions per area
            - batch: all questions dumped as a list
            - auto: each question gets the recommended default answer

    Returns:
        List of question dicts with area_index, question, options, default.
    """
    questions: list[dict] = []

    for idx, area in enumerate(gray_areas):
        topic = area["topic"]
        options = [opt["name"] for opt in area.get("options", [])]
        recommendation = area.get("recommendation", options[0] if options else "")

        # Primary question: which approach
        primary = {
            "area_index": idx,
            "question": f"Which approach for: {topic}?",
            "options": options,
            "default": recommendation,
        }

        if mode == "auto":
            primary["answer"] = recommendation

        questions.append(primary)

        # Secondary question for interactive mode: any constraints
        if mode == "interactive" and area.get("context"):
            secondary = {
                "area_index": idx,
                "question": (
                    f"Any constraints or preferences for {topic.lower()}? "
                    f"(Context: {area['context']})"
                ),
                "options": ["No constraints", "Yes — will specify"],
                "default": "No constraints",
            }
            questions.append(secondary)

    return questions


@retry_on_busy()
def apply_answers(
    conn: sqlite3.Connection,
    phase_id: int,
    project_id: str,
    gray_areas: list[dict],
    answers: list[dict],
    project_dir: Path,
) -> dict:
    """Persist answers as decisions and log to discussion trail.

    Args:
        conn: Database connection.
        phase_id: Phase these decisions belong to.
        project_id: Project identifier.
        gray_areas: The gray areas that were discussed.
        answers: List of dicts with area_index and answer keys.
        project_dir: Project root for discussion log.

    Returns:
        Dict with 'decisions' (list of created decision dicts) and
        'context_doc' (generated CONTEXT.md string).
    """
    decisions: list[dict] = []

    for answer in answers:
        area_idx = answer.get("area_index", 0)
        if area_idx >= len(gray_areas):
            logger.warning("Skipping answer with out-of-range area_index=%d", area_idx)
            continue

        area = gray_areas[area_idx]
        chosen = answer.get("answer", area.get("recommendation", ""))
        topic = area["topic"]
        raw_category = area.get("category", "approach")
        category = _CATEGORY_TO_DB.get(raw_category, "approach")

        # Persist as a decision
        decision = create_decision(
            conn,
            summary=f"{topic}: {chosen}",
            category=category,
            rationale=area.get("context", ""),
            project_id=project_id,
            phase_id=phase_id,
        )
        decisions.append(decision)

        # Log to discussion trail
        log_discussion(
            project_dir=project_dir,
            topic=topic,
            options=area.get("options", []),
            decision=chosen,
            rationale=area.get("context", ""),
            decision_id=decision.get("decision_id", ""),
        )

        logger.info(
            "Decision recorded: %s -> %s (phase=%d)",
            topic,
            chosen,
            phase_id,
        )

    # Build context doc from phase + all decisions
    phase = get_phase(conn, phase_id)
    all_decisions = list_decisions(conn, project_id=project_id, phase_id=phase_id)
    context_doc = generate_context_doc(phase or {}, all_decisions)

    return {
        "decisions": decisions,
        "context_doc": context_doc,
    }


def generate_context_doc(
    phase: dict,
    decisions: list[dict],
    prior_context: str | None = None,
) -> str:
    """Build a CONTEXT.md string for the phase.

    Sections:
        - ## Domain — phase name and description
        - ## Decisions — each decision with ID and rationale
        - ## Code Context — prior context or placeholder
        - ## Deferred — items explicitly deferred
    """
    lines: list[str] = ["# Phase Context\n"]

    # Domain section
    lines.append("## Domain\n")
    phase_name = phase.get("name", "Unknown")
    phase_desc = phase.get("description", "No description provided.")
    lines.append(f"**Phase:** {phase_name}\n")
    lines.append(f"{phase_desc}\n")

    # Acceptance criteria if present
    criteria_raw = phase.get("acceptance_criteria")
    if criteria_raw:
        if isinstance(criteria_raw, str):
            try:
                criteria = json.loads(criteria_raw)
            except (json.JSONDecodeError, TypeError):
                criteria = [criteria_raw]
        else:
            criteria = criteria_raw
        if criteria:
            lines.append("**Acceptance Criteria:**\n")
            for c in criteria:
                lines.append(f"- {c}")
            lines.append("")

    # Decisions section
    lines.append("## Decisions\n")
    if decisions:
        for d in decisions:
            dec_id = d.get("decision_id", "N/A")
            summary = d.get("summary", "")
            rationale = d.get("rationale", "")
            lines.append(f"- **[{dec_id}]** {summary}")
            if rationale:
                lines.append(f"  - Rationale: {rationale}")
        lines.append("")
    else:
        lines.append("No decisions recorded yet.\n")

    # Code Context section
    lines.append("## Code Context\n")
    if prior_context:
        lines.append(f"{prior_context}\n")
    else:
        lines.append("No prior code context.\n")

    # Deferred section
    lines.append("## Deferred\n")
    deferred = [d for d in decisions if d.get("category") == "deferred"]
    if deferred:
        for d in deferred:
            lines.append(f"- {d.get('summary', '')}")
        lines.append("")
    else:
        lines.append("No deferred items.\n")

    return "\n".join(lines)


def run_discuss(
    conn: sqlite3.Connection,
    phase_id: int,
    project_id: str,
    project_dir: Path,
    mode: str = "interactive",
    chain: bool = False,
) -> dict:
    """Main orchestrator: identify gray areas, generate questions, optionally apply.

    Args:
        conn: Database connection.
        phase_id: Phase to discuss.
        project_id: Project identifier.
        project_dir: Project root directory.
        mode: One of 'interactive', 'batch', or 'auto'.
        chain: If True, indicates this is part of a chained workflow.

    Returns:
        Dict with phase_id, gray_areas, questions, mode, context_doc, chain.
        If mode='auto', answers are applied and context_doc is populated.
    """
    phase = get_phase(conn, phase_id)
    if not phase:
        logger.error("Phase %d not found", phase_id)
        return {
            "phase_id": phase_id,
            "gray_areas": [],
            "questions": [],
            "mode": mode,
            "context_doc": None,
            "chain": chain,
            "error": f"Phase {phase_id} not found",
        }

    phase_name = phase.get("name", "")
    phase_desc = phase.get("description", "")

    # Parse acceptance criteria
    criteria_raw = phase.get("acceptance_criteria")
    if isinstance(criteria_raw, str):
        try:
            acceptance_criteria = json.loads(criteria_raw)
        except (json.JSONDecodeError, TypeError):
            acceptance_criteria = [criteria_raw] if criteria_raw else []
    elif isinstance(criteria_raw, list):
        acceptance_criteria = criteria_raw
    else:
        acceptance_criteria = []

    # Load prior decisions for this phase
    prior_decisions = list_decisions(conn, project_id=project_id, phase_id=phase_id)

    # Identify gray areas
    gray_areas = identify_gray_areas(
        phase_name=phase_name,
        phase_description=phase_desc,
        acceptance_criteria=acceptance_criteria,
        prior_decisions=prior_decisions,
    )

    # Generate questions
    questions = generate_questions(gray_areas, mode=mode)

    context_doc: str | None = None

    # In auto mode, apply recommended answers immediately
    if mode == "auto" and gray_areas:
        auto_answers = [
            {
                "area_index": idx,
                "answer": area.get("recommendation", ""),
            }
            for idx, area in enumerate(gray_areas)
        ]
        result = apply_answers(conn, phase_id, project_id, gray_areas, auto_answers, project_dir)
        context_doc = result["context_doc"]
        logger.info(
            "Auto-applied %d decisions for phase %d",
            len(result["decisions"]),
            phase_id,
        )
    elif not gray_areas:
        # No gray areas — still generate context doc from existing decisions
        context_doc = generate_context_doc(phase, prior_decisions)

    return {
        "phase_id": phase_id,
        "gray_areas": gray_areas,
        "questions": questions,
        "mode": mode,
        "context_doc": context_doc,
        "chain": chain,
    }
