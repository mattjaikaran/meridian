#!/usr/bin/env python3
"""Persona system — load and apply role-typed prompt templates for reviews, discuss, and dispatch."""

from pathlib import Path

_KNOWN_PERSONAS = {"pm", "architect", "ux", "qa", "security"}

_PERSONA_LABELS = {
    "pm": "Product Manager",
    "architect": "Software Architect",
    "ux": "UX / Design",
    "qa": "QA / Testing",
    "security": "Security Engineer",
}


def _prompts_dir(meridian_home: str | Path | None = None) -> Path:
    if meridian_home:
        return Path(meridian_home) / "prompts"
    home = Path(__file__).parent.parent
    return home / "prompts"


def list_personas(meridian_home: str | Path | None = None) -> list[dict]:
    """Return list of available personas with name, label, and path."""
    prompts = _prompts_dir(meridian_home)
    result = []
    for name in sorted(_KNOWN_PERSONAS):
        path = prompts / f"{name}.md"
        result.append(
            {
                "name": name,
                "label": _PERSONA_LABELS.get(name, name.title()),
                "path": str(path),
                "available": path.exists(),
            }
        )
    return result


def load_persona(name: str, meridian_home: str | Path | None = None) -> dict:
    """Load a persona prompt by name.

    Returns dict with keys: name, label, content, path.
    Raises ValueError for unknown names. Raises FileNotFoundError if file missing.
    """
    name = name.lower().strip()
    if name not in _KNOWN_PERSONAS:
        available = ", ".join(sorted(_KNOWN_PERSONAS))
        raise ValueError(f"Unknown persona '{name}'. Available: {available}")

    path = _prompts_dir(meridian_home) / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: {path}")

    content = path.read_text(encoding="utf-8")
    return {
        "name": name,
        "label": _PERSONA_LABELS.get(name, name.title()),
        "content": content,
        "path": str(path),
    }


def apply_persona(base_prompt: str, persona_name: str, meridian_home: str | Path | None = None) -> str:
    """Prepend persona lens to an existing prompt template.

    Returns the combined prompt: persona instructions followed by the base prompt,
    separated by a clear divider.
    """
    persona = load_persona(persona_name, meridian_home)
    divider = "\n\n---\n\n"
    return persona["content"] + divider + base_prompt


def persona_header(persona_name: str, meridian_home: str | Path | None = None) -> str:
    """Return just the persona header block (first paragraph) for inline injection.

    Useful when you only want the role framing, not the full instruction set.
    """
    persona = load_persona(persona_name, meridian_home)
    lines = persona["content"].splitlines()
    header_lines = []
    for line in lines:
        if line.startswith("## ") and header_lines:
            break
        header_lines.append(line)
    return "\n".join(header_lines).strip()
