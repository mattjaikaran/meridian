---
phase: 3
slug: command-routing
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-11
wave_0_validated: "2026-03-16T16:51:59Z"
---
# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via uv) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_generate_commands.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_generate_commands.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | ROUT-01 | unit | `uv run pytest tests/test_generate_commands.py::test_discover_all_skills -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | ROUT-02 | unit | `uv run pytest tests/test_generate_commands.py::test_wrapper_format -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | ROUT-03 | unit | `uv run pytest tests/test_generate_commands.py::test_generate_end_to_end -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | ROUT-03 | unit | `uv run pytest tests/test_generate_commands.py::test_preserve_custom_files -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | ROUT-03 | unit | `uv run pytest tests/test_generate_commands.py::test_cleanup_orphans -x` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | ROUT-03 | unit | `uv run pytest tests/test_generate_commands.py::test_uninstall -x` | ❌ W0 | ⬜ pending |
| 03-01-07 | 01 | 1 | ROUT-03 | unit | `uv run pytest tests/test_generate_commands.py::test_fix_symlink -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | ROUT-04 | unit | `uv run pytest tests/test_generate_commands.py::test_root_skill_no_commands -x` | ❌ W0 | ⬜ pending |
| 03-manual | - | - | ROUT-01 | manual-only | N/A (requires Claude Code session) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_generate_commands.py` — stubs for ROUT-01 through ROUT-04 (unit tests with tmp_path fixtures)
- [ ] Tests should use `tmp_path` for both skills source dir and commands output dir (no touching real `~/.claude/`)

*Existing pytest infrastructure covers framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Typing `/meridian:` shows all 13 commands in Claude Code autocomplete | ROUT-01 | Requires live Claude Code session | 1. Run generator 2. Open Claude Code 3. Type `/meridian:` 4. Verify all 13 subcommands appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
