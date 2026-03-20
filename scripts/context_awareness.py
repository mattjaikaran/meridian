#!/usr/bin/env python3
"""Context window awareness for optimal prompt sizing.

Detects context window size from model metadata or config, allocates
budget across prompt sections, and trims content to fit within budget.

Budget allocation:
  - 10% system prompt
  - 20% plan description
  - 50% code context
  - 20% tools / reserve
"""

import logging
import os
from dataclasses import dataclass

from scripts.context_window import estimate_tokens

logger = logging.getLogger(__name__)

# Known model context sizes (tokens)
MODEL_CONTEXT_SIZES: dict[str, int] = {
    "claude-opus-4-6": 1_000_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-haiku-3.5": 200_000,
}

# Default context size when model is unknown
DEFAULT_CONTEXT_SIZE: int = 200_000

# Large context threshold — models above this get full file contents
LARGE_CONTEXT_THRESHOLD: int = 500_000

# Warning threshold — emit warning when prompt exceeds this fraction of budget
WARNING_THRESHOLD: float = 0.80

# Budget allocation fractions
SYSTEM_FRACTION: float = 0.10
PLAN_FRACTION: float = 0.20
CODE_FRACTION: float = 0.50
RESERVE_FRACTION: float = 0.20


@dataclass
class ContextBudget:
    """Token budget allocation for prompt sections."""

    total: int
    system: int
    plan: int
    code: int
    reserve: int

    @property
    def is_large_context(self) -> bool:
        """Whether this budget has large context (1M+)."""
        return self.total >= LARGE_CONTEXT_THRESHOLD


def detect_context_size(
    model: str | None = None,
    override: int | None = None,
) -> int:
    """Detect context window size for the current model.

    Priority:
    1. Explicit override parameter
    2. MERIDIAN_CONTEXT_SIZE environment variable
    3. Known model lookup
    4. Default (200k)

    Args:
        model: Model identifier (e.g. "claude-opus-4-6").
        override: Explicit context size override.

    Returns:
        Context window size in tokens.
    """
    if override is not None:
        return override

    env_size = os.environ.get("MERIDIAN_CONTEXT_SIZE")
    if env_size is not None:
        try:
            return int(env_size)
        except ValueError:
            logger.warning("Invalid MERIDIAN_CONTEXT_SIZE: %s, using default", env_size)

    if model and model in MODEL_CONTEXT_SIZES:
        return MODEL_CONTEXT_SIZES[model]

    return DEFAULT_CONTEXT_SIZE


def allocate_context_budget(
    total: int | None = None,
    model: str | None = None,
) -> ContextBudget:
    """Allocate context budget across prompt sections.

    Budget split: 10% system, 20% plan, 50% code, 20% reserve.

    Args:
        total: Total context size. If None, auto-detected.
        model: Model identifier for auto-detection.

    Returns:
        ContextBudget with allocated token counts.
    """
    if total is None:
        total = detect_context_size(model=model)

    return ContextBudget(
        total=total,
        system=int(total * SYSTEM_FRACTION),
        plan=int(total * PLAN_FRACTION),
        code=int(total * CODE_FRACTION),
        reserve=int(total * RESERVE_FRACTION),
    )


def trim_to_budget(
    content: str,
    budget_tokens: int,
    strategy: str = "tail",
) -> tuple[str, bool]:
    """Trim content to fit within a token budget.

    Args:
        content: Text content to potentially trim.
        budget_tokens: Maximum tokens allowed.
        strategy: Trimming strategy — "tail" keeps the end (most recent),
                  "head" keeps the beginning.

    Returns:
        Tuple of (trimmed_content, was_trimmed).
    """
    current = estimate_tokens(content)
    if current <= budget_tokens:
        return content, False

    if budget_tokens <= 0:
        return "", True

    # Estimate chars allowed from budget
    # estimate_tokens uses TOKENS_PER_CHAR = 0.3, so chars = tokens / 0.3
    from scripts.context_window import TOKENS_PER_CHAR

    max_chars = int(budget_tokens / TOKENS_PER_CHAR)

    if strategy == "head":
        trimmed = content[:max_chars]
        suffix = "\n\n... [trimmed: content truncated to fit budget]"
        trimmed = trimmed[: max_chars - len(suffix)] + suffix
    else:  # tail — keep the end (most recent context)
        trimmed = content[-max_chars:]
        prefix = "[trimmed: earlier content removed to fit budget] ...\n\n"
        trimmed = prefix + trimmed[len(prefix):]

    return trimmed, True


def check_budget_warning(
    used_tokens: int,
    budget: ContextBudget,
) -> str | None:
    """Check if token usage exceeds warning threshold.

    Args:
        used_tokens: Total tokens used across all sections.
        budget: The allocated budget.

    Returns:
        Warning message if over 80% of total budget, None otherwise.
    """
    ratio = used_tokens / budget.total if budget.total > 0 else 1.0
    if ratio >= WARNING_THRESHOLD:
        pct = int(ratio * 100)
        return (
            f"Context usage at {pct}% ({used_tokens:,} / {budget.total:,} tokens). "
            f"Consider using summaries or reducing included files."
        )
    return None
