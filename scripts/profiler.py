#!/usr/bin/env python3
"""Meridian developer profiler — analyze project to build developer preference profile."""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

# Profile output location
PROFILE_FILENAME = "USER-PROFILE.md"


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _profile_path(project_dir: Path) -> Path:
    """Get the path to the profile file."""
    return project_dir / ".meridian" / PROFILE_FILENAME


def analyze_project_patterns(project_dir: Path) -> dict:
    """Analyze the project to extract developer patterns.

    Examines git history, file structure, and config files to build
    a profile of development preferences.

    Args:
        project_dir: Root directory of the project.

    Returns:
        Dict with keys: commit_style, languages, frameworks,
        branch_style, test_style, structure.
    """
    patterns: dict = {
        "commit_style": _analyze_commit_style(project_dir),
        "languages": _analyze_languages(project_dir),
        "frameworks": _detect_frameworks(project_dir),
        "branch_style": _analyze_branch_style(project_dir),
        "test_style": _analyze_test_style(project_dir),
        "structure": _analyze_structure(project_dir),
    }
    return patterns


def _analyze_commit_style(project_dir: Path) -> dict:
    """Analyze git commit message patterns."""
    log = _run_git(["log", "--oneline", "-50", "--format=%s"], project_dir)
    if not log:
        return {"convention": "unknown", "sample_count": 0}

    messages = log.splitlines()
    conventional = 0
    for msg in messages:
        if re.match(r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build)\b", msg):
            conventional += 1

    ratio = conventional / len(messages) if messages else 0
    convention = "conventional" if ratio > 0.5 else "freeform"

    return {
        "convention": convention,
        "sample_count": len(messages),
        "conventional_ratio": round(ratio, 2),
    }


def _analyze_languages(project_dir: Path) -> list[str]:
    """Detect languages used in the project by file extensions."""
    ext_map = {
        ".py": "Python",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".rs": "Rust",
        ".go": "Go",
        ".swift": "Swift",
        ".cpp": "C++",
        ".c": "C",
        ".java": "Java",
        ".rb": "Ruby",
    }

    found: set[str] = set()
    try:
        for ext, lang in ext_map.items():
            # Check if any files with this extension exist (non-recursively into
            # hidden dirs / node_modules would be noisy, so use git ls-files)
            files = _run_git(["ls-files", f"*{ext}"], project_dir)
            if files:
                found.add(lang)
    except Exception:
        pass

    # Fallback: scan directory directly
    if not found:
        for ext, lang in ext_map.items():
            if list(project_dir.glob(f"**/*{ext}"))[:1]:
                found.add(lang)

    return sorted(found)


def _detect_frameworks(project_dir: Path) -> list[str]:
    """Detect frameworks from config files."""
    framework_markers = {
        "pyproject.toml": "Python (pyproject)",
        "setup.py": "Python (setuptools)",
        "package.json": "Node.js",
        "Cargo.toml": "Rust (Cargo)",
        "go.mod": "Go (modules)",
        "Gemfile": "Ruby (Bundler)",
        "requirements.txt": "Python (pip)",
        "docker-compose.yml": "Docker Compose",
        "docker-compose.yaml": "Docker Compose",
        "Dockerfile": "Docker",
        ".github/workflows": "GitHub Actions",
        "Makefile": "Make",
    }

    found: list[str] = []
    for marker, name in framework_markers.items():
        path = project_dir / marker
        if path.exists():
            found.append(name)

    return sorted(set(found))


def _analyze_branch_style(project_dir: Path) -> dict:
    """Analyze branch naming conventions."""
    branches = _run_git(["branch", "-a", "--format=%(refname:short)"], project_dir)
    if not branches:
        return {"convention": "unknown", "sample_count": 0}

    branch_list = branches.splitlines()
    prefixed = 0
    for b in branch_list:
        if re.match(r"^(feature|fix|refactor|chore|hotfix|release)/", b):
            prefixed += 1

    ratio = prefixed / len(branch_list) if branch_list else 0
    convention = "prefixed" if ratio > 0.3 else "flat"

    return {
        "convention": convention,
        "sample_count": len(branch_list),
        "prefixed_ratio": round(ratio, 2),
    }


def _analyze_test_style(project_dir: Path) -> dict:
    """Detect testing patterns."""
    test_dirs = []
    for candidate in ["tests", "test", "spec", "__tests__"]:
        if (project_dir / candidate).is_dir():
            test_dirs.append(candidate)

    # Detect test framework markers
    frameworks: list[str] = []
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "pytest" in content:
            frameworks.append("pytest")
        if "unittest" in content:
            frameworks.append("unittest")

    if (project_dir / "jest.config.js").exists() or (project_dir / "jest.config.ts").exists():
        frameworks.append("jest")

    return {
        "test_dirs": test_dirs,
        "frameworks": frameworks,
    }


def _analyze_structure(project_dir: Path) -> dict:
    """Analyze project directory structure conventions."""
    notable_dirs = []
    for d in sorted(project_dir.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and d.name != "__pycache__":
            notable_dirs.append(d.name)

    config_files = []
    for f in sorted(project_dir.iterdir()):
        if f.is_file() and (f.name.startswith(".") or f.suffix in {".toml", ".yaml", ".yml", ".json", ".cfg"}):
            if f.name not in {".DS_Store"}:
                config_files.append(f.name)

    return {
        "top_level_dirs": notable_dirs[:20],
        "config_files": config_files[:20],
    }


def generate_profile(patterns: dict) -> str:
    """Generate a USER-PROFILE.md content from analyzed patterns.

    Args:
        patterns: Dict from analyze_project_patterns().

    Returns:
        Markdown string for the profile.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Developer Profile",
        "",
        f"_Generated: {now}_",
        "",
    ]

    # Commit style
    cs = patterns.get("commit_style", {})
    lines.append("## Commit Style")
    lines.append(f"- Convention: **{cs.get('convention', 'unknown')}**")
    if "conventional_ratio" in cs:
        lines.append(f"- Conventional commit ratio: {cs['conventional_ratio']}")
    lines.append(f"- Sample size: {cs.get('sample_count', 0)} commits")
    lines.append("")

    # Languages
    langs = patterns.get("languages", [])
    lines.append("## Languages")
    if langs:
        for lang in langs:
            lines.append(f"- {lang}")
    else:
        lines.append("- No language files detected")
    lines.append("")

    # Frameworks
    fws = patterns.get("frameworks", [])
    lines.append("## Frameworks & Tools")
    if fws:
        for fw in fws:
            lines.append(f"- {fw}")
    else:
        lines.append("- None detected")
    lines.append("")

    # Branch style
    bs = patterns.get("branch_style", {})
    lines.append("## Branch Naming")
    lines.append(f"- Convention: **{bs.get('convention', 'unknown')}**")
    if "prefixed_ratio" in bs:
        lines.append(f"- Prefixed ratio: {bs['prefixed_ratio']}")
    lines.append("")

    # Test style
    ts = patterns.get("test_style", {})
    lines.append("## Testing")
    test_dirs = ts.get("test_dirs", [])
    test_fws = ts.get("frameworks", [])
    if test_dirs:
        lines.append(f"- Test directories: {', '.join(test_dirs)}")
    if test_fws:
        lines.append(f"- Frameworks: {', '.join(test_fws)}")
    if not test_dirs and not test_fws:
        lines.append("- No test infrastructure detected")
    lines.append("")

    # Structure
    st = patterns.get("structure", {})
    lines.append("## Project Structure")
    top_dirs = st.get("top_level_dirs", [])
    if top_dirs:
        lines.append(f"- Top-level dirs: {', '.join(top_dirs)}")
    config_files = st.get("config_files", [])
    if config_files:
        lines.append(f"- Config files: {', '.join(config_files)}")
    lines.append("")

    return "\n".join(lines)


def save_profile(project_dir: Path, content: str) -> Path:
    """Save profile content to .meridian/USER-PROFILE.md.

    Args:
        project_dir: Project root directory.
        content: Markdown content to write.

    Returns:
        Path to the saved profile file.
    """
    profile_file = _profile_path(project_dir)
    profile_file.parent.mkdir(parents=True, exist_ok=True)
    profile_file.write_text(content, encoding="utf-8")
    return profile_file
