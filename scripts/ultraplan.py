#!/usr/bin/env python3
"""Ultraplan — cloud-accelerated planning with local fallback."""

import json
import urllib.error
import urllib.request
from pathlib import Path

from scripts.db import open_project
from scripts.logging_config import get_logger
from scripts.state import get_phase, get_project, get_status

logger = get_logger("meridian.ultraplan")

_MIN_CC_VERSION = (2, 1, 91)


def _parse_version(version_str: str) -> tuple[int, ...] | None:
    """Parse 'vX.Y.Z' or 'X.Y.Z' into a tuple, or None on failure."""
    try:
        clean = version_str.lstrip("v")
        return tuple(int(p) for p in clean.split(".")[:3])
    except (ValueError, AttributeError):
        return None


def _detect_cc_version() -> str | None:
    """Attempt to detect the running Claude Code version from the environment."""
    import subprocess

    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            line = result.stdout.strip().splitlines()[0]
            # Format: "claude X.Y.Z" or just "X.Y.Z"
            parts = line.split()
            return parts[-1] if parts else None
    except Exception:
        pass
    return None


def check_ultraplan_availability(project_dir: str | Path = ".") -> dict:
    """Check whether the cloud ultraplan backend is reachable and configured.

    Returns dict with keys:
        available (bool), version (str|None), mode ('cloud'|'local'), reason (str)
    """
    project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn)

    config: dict = {}
    if project and project.get("settings"):
        try:
            config = json.loads(project["settings"])
        except (json.JSONDecodeError, TypeError):
            config = {}

    # Check feature flag
    if not config.get("ultraplan_enabled", False):
        return {
            "available": False,
            "version": None,
            "mode": "local",
            "reason": "ultraplan_enabled not set in project config",
        }

    endpoint: str | None = config.get("ultraplan_endpoint")
    if not endpoint:
        return {
            "available": False,
            "version": None,
            "mode": "local",
            "reason": "ultraplan_endpoint not configured (set via /meridian:config)",
        }

    # Check Claude Code version
    cc_version_str = _detect_cc_version()
    if cc_version_str:
        parsed = _parse_version(cc_version_str)
        if parsed and parsed < _MIN_CC_VERSION:
            min_str = ".".join(str(x) for x in _MIN_CC_VERSION)
            return {
                "available": False,
                "version": cc_version_str,
                "mode": "local",
                "reason": f"Claude Code {cc_version_str} < {min_str} required for cloud planning",
            }

    # Ping the endpoint health check
    try:
        req = urllib.request.Request(
            f"{endpoint.rstrip('/')}/health",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("status") not in ("ok", "healthy"):
                return {
                    "available": False,
                    "version": cc_version_str,
                    "mode": "local",
                    "reason": f"Cloud endpoint returned unhealthy status: {body.get('status')}",
                }
    except urllib.error.URLError as exc:
        logger.debug("Cloud endpoint unreachable: %s", exc)
        return {
            "available": False,
            "version": cc_version_str,
            "mode": "local",
            "reason": f"Cloud endpoint unreachable: {exc}",
        }
    except Exception as exc:
        logger.debug("Cloud availability check failed: %s", exc)
        return {
            "available": False,
            "version": cc_version_str,
            "mode": "local",
            "reason": f"Availability check error: {exc}",
        }

    return {
        "available": True,
        "version": cc_version_str,
        "mode": "cloud",
        "reason": "Cloud backend reachable and configured",
    }


def run_cloud_plan(
    project_dir: str | Path = ".",
    phase_id: int | None = None,
    goal: str = "",
) -> dict:
    """Send phase context to cloud planning backend and return plan result.

    Returns dict with keys:
        status ('success'|'failed'), plans (list), artifact_paths (list), error (str|None)
    """
    project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn)
        status = get_status(conn)

        config: dict = {}
        if project and project.get("settings"):
            try:
                config = json.loads(project["settings"])
            except (json.JSONDecodeError, TypeError):
                config = {}

        endpoint: str | None = config.get("ultraplan_endpoint")
        if not endpoint:
            return {"status": "failed", "error": "ultraplan_endpoint not configured", "plans": [], "artifact_paths": []}

        # Resolve target phase
        target_phase = None
        if phase_id is not None:
            target_phase = get_phase(conn, phase_id)
        else:
            active = status.get("active_phase")
            if active:
                target_phase = active

        if target_phase is None:
            return {"status": "failed", "error": "No phase to plan. Run /meridian:plan first.", "plans": [], "artifact_paths": []}

        payload = {
            "project_name": project.get("name", "unknown") if project else "unknown",
            "phase_id": target_phase.get("id"),
            "phase_name": target_phase.get("name"),
            "description": target_phase.get("description", ""),
            "acceptance_criteria": target_phase.get("acceptance_criteria", ""),
            "tech_stack": target_phase.get("tech_stack", ""),
            "goal": goal,
        }

    url = f"{endpoint.rstrip('/')}/plan"
    logger.info("Sending plan request to cloud backend: %s", url)

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "success",
                "plans": result.get("plans", []),
                "artifact_paths": result.get("artifact_paths", []),
                "error": None,
            }
    except urllib.error.URLError as exc:
        logger.error("Cloud plan request failed: %s", exc)
        return {"status": "failed", "error": str(exc), "plans": [], "artifact_paths": []}
    except Exception as exc:
        logger.error("Cloud plan error: %s", exc)
        return {"status": "failed", "error": str(exc), "plans": [], "artifact_paths": []}
