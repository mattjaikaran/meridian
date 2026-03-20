#!/usr/bin/env python3
"""Centralized security utilities for input validation.

Provides path traversal protection, safe JSON parsing, SQL identifier
validation, and shell argument sanitization. All functions are stdlib-only.
"""

import json
import re
from pathlib import Path

from scripts.db import MeridianError

# Shell metacharacters that could enable injection
_DANGEROUS_SHELL_CHARS = re.compile(r"[;|&$`\\\"'\n\r\x00()<>{}!#~]")

# SQL-safe identifier: starts with letter or underscore, contains only
# alphanumerics and underscores
_FIELD_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Maximum size for JSON input (1 MB)
_JSON_MAX_SIZE = 1_048_576


def validate_path(path: str | Path, project_root: str | Path) -> Path:
    """Resolve *path* and reject if it escapes *project_root*.

    Resolves symlinks on both arguments so that ``../`` tricks and symlink
    attacks are caught. Returns the resolved :class:`Path` on success.

    Raises:
        MeridianError: If the resolved path is not inside project_root.
    """
    resolved = Path(path).resolve()
    root = Path(project_root).resolve()
    # Use os.path approach: resolved must start with root
    try:
        resolved.relative_to(root)
    except ValueError:
        raise MeridianError(
            f"Path escapes project root: {path!r} resolves to {resolved}"
        )
    return resolved


def safe_json_loads(text: str) -> dict | None:
    """Parse *text* as JSON with size guard.

    Returns the parsed dict/list on success, or ``None`` on any failure
    (malformed JSON, size exceeded, wrong type).
    """
    if not isinstance(text, str):
        return None
    if len(text) > _JSON_MAX_SIZE:
        return None
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(result, (dict, list)):
        return None
    return result


def validate_field_name(name: str) -> str:
    """Validate that *name* is a SQL-safe identifier.

    Only allows ``[a-zA-Z_][a-zA-Z0-9_]*``. Returns the name unchanged on
    success.

    Raises:
        MeridianError: If the name contains unsafe characters.
    """
    if not isinstance(name, str) or not _FIELD_NAME_RE.match(name):
        raise MeridianError(f"Invalid field name: {name!r}")
    return name


def sanitize_shell_arg(arg: str) -> str:
    """Reject *arg* if it contains dangerous shell metacharacters.

    Returns the argument unchanged if safe.

    Raises:
        MeridianError: If the argument contains shell metacharacters.
    """
    if not isinstance(arg, str):
        raise MeridianError(f"Shell argument must be a string, got {type(arg).__name__}")
    if _DANGEROUS_SHELL_CHARS.search(arg):
        raise MeridianError(f"Shell argument contains dangerous characters: {arg!r}")
    return arg
