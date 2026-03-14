#!/usr/bin/env python3
"""Git state validation — verify DB state matches git reality."""

import sqlite3
import subprocess


def validate_state(conn: sqlite3.Connection, repo_path: str = ".") -> dict[str, list[int]]:
    """Check completed plans with commit_sha against the git repo.

    Returns:
        {valid: [plan_ids], drift: [], missing: [plan_ids]}
        - valid: SHA exists in git
        - drift: (reserved for future: SHA exists but content differs)
        - missing: SHA does not exist in git
    """
    rows = conn.execute(
        "SELECT id, name, commit_sha FROM plan WHERE status = 'complete'"
    ).fetchall()

    valid = []
    drift = []
    missing = []

    for row in rows:
        plan_id = row["id"]
        sha = row["commit_sha"]

        if not sha:
            # No SHA recorded — skip (not an error, just no commit tracked)
            continue

        try:
            result = subprocess.run(
                ["git", "cat-file", "-t", sha],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            if result.returncode == 0:
                valid.append(plan_id)
            else:
                missing.append(plan_id)
        except (OSError, subprocess.SubprocessError):
            missing.append(plan_id)

    return {"valid": valid, "drift": drift, "missing": missing}
