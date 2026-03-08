#!/usr/bin/env python3
"""Token estimation and checkpoint trigger management."""

# Rough token estimates for context tracking.
# Not exact — used for checkpoint trigger decisions, not billing.

# Average tokens per character (English text + code mix)
TOKENS_PER_CHAR = 0.3

# Checkpoint threshold
AUTO_CHECKPOINT_TOKENS = 150_000

# Subagent fresh context budget
SUBAGENT_CONTEXT_BUDGET = 200_000


def estimate_tokens(text: str) -> int:
    """Rough token estimate from character count."""
    return int(len(text) * TOKENS_PER_CHAR)


def estimate_file_tokens(file_path: str) -> int:
    """Estimate tokens in a file."""
    try:
        with open(file_path) as f:
            return estimate_tokens(f.read())
    except (OSError, UnicodeDecodeError):
        return 0


def should_checkpoint(estimated_tokens: int) -> bool:
    """Check if we should trigger an auto-checkpoint."""
    return estimated_tokens >= AUTO_CHECKPOINT_TOKENS


def estimate_plan_context(
    plan_description: str,
    context_doc: str | None = None,
    file_paths: list[str] | None = None,
) -> int:
    """Estimate total token usage for executing a plan."""
    total = estimate_tokens(plan_description)

    if context_doc:
        total += estimate_tokens(context_doc)

    if file_paths:
        for path in file_paths:
            total += estimate_file_tokens(path)

    # Add overhead for prompt templates, system prompts, etc.
    total += 5000

    return total


def fits_in_subagent(estimated_tokens: int) -> bool:
    """Check if a plan's context fits in a subagent's budget."""
    return estimated_tokens < SUBAGENT_CONTEXT_BUDGET


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
        tokens = estimate_file_tokens(path)
        print(f"{path}: ~{tokens:,} tokens")
    else:
        print("Usage: python context_window.py <file_path>")
