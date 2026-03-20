#!/usr/bin/env python3
"""PR branch creation — filter planning-only commits for clean PRs.

Creates a ``pr/<slug>`` branch containing only commits that touch code files
(i.e., files outside ``.planning/`` and ``.meridian/``). Uses cherry-pick to
preserve the original branch untouched.
"""

import subprocess
from pathlib import Path

from scripts.db import MeridianError

# Directories whose changes are considered "planning artifacts"
_PLANNING_PREFIXES = (".planning/", ".meridian/")


def _run_git(args: list[str], cwd: str | Path | None = None) -> str:
    """Run a git command and return stripped stdout.

    Raises MeridianError on non-zero exit.
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise MeridianError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def has_code_changes(commit_sha: str, cwd: str | Path | None = None) -> bool:
    """Check whether *commit_sha* touches files outside planning directories.

    Returns True if at least one changed file is NOT under ``.planning/``
    or ``.meridian/``.
    """
    output = _run_git(
        ["diff-tree", "--no-commit-id", "-r", "--name-only", commit_sha],
        cwd=cwd,
    )
    if not output:
        return False
    for line in output.splitlines():
        if not any(line.startswith(prefix) for prefix in _PLANNING_PREFIXES):
            return True
    return False


def filter_commits(
    base_branch: str = "main",
    cwd: str | Path | None = None,
) -> list[str]:
    """List commit SHAs since *base_branch* that contain code changes.

    Returns commits in chronological order (oldest first) suitable for
    cherry-picking.
    """
    output = _run_git(
        ["rev-list", "--reverse", f"{base_branch}..HEAD"],
        cwd=cwd,
    )
    if not output:
        return []
    all_shas = output.splitlines()
    return [sha for sha in all_shas if has_code_changes(sha, cwd=cwd)]


def create_pr_branch(
    slug: str,
    base_branch: str = "main",
    cwd: str | Path | None = None,
) -> str:
    """Create a ``pr/<slug>`` branch with only code-relevant commits.

    1. Identifies commits since *base_branch* with code changes.
    2. Creates ``pr/<slug>`` from *base_branch*.
    3. Cherry-picks the filtered commits onto the new branch.
    4. Returns to the original branch.

    Returns the new branch name.

    Raises:
        MeridianError: If no code commits found or cherry-pick fails.
    """
    code_commits = filter_commits(base_branch, cwd=cwd)
    if not code_commits:
        raise MeridianError(
            "No code commits found — all commits are planning-only"
        )

    original_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    branch_name = f"pr/{slug}"

    # Create the PR branch from base
    _run_git(["checkout", "-b", branch_name, base_branch], cwd=cwd)

    try:
        for sha in code_commits:
            _run_git(["cherry-pick", sha], cwd=cwd)
    except MeridianError:
        # Abort cherry-pick and return to original branch on failure
        subprocess.run(
            ["git", "cherry-pick", "--abort"],
            capture_output=True,
            cwd=cwd,
        )
        _run_git(["checkout", original_branch], cwd=cwd)
        _run_git(["branch", "-D", branch_name], cwd=cwd)
        raise MeridianError(
            f"Cherry-pick failed — conflicts detected. "
            f"Clean branch {branch_name} was removed."
        )

    # Return to original branch
    _run_git(["checkout", original_branch], cwd=cwd)

    return branch_name
