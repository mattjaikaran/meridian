# Contributing to Meridian

Contributions are welcome. This guide covers development setup, testing, and how to submit changes.

## Development Setup

```bash
# Clone
git clone https://github.com/mattjaikaran/meridian.git
cd meridian

# Install dependencies (pytest only)
uv sync

# Run tests to verify your setup
uv run pytest tests/ -v
```

### Requirements

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **git**

## Project Structure

```
scripts/          # Core Python modules (stdlib only, no external deps)
skills/           # Slash command definitions (SKILL.md per command)
tests/            # pytest test suite
prompts/          # Subagent prompt templates
references/       # Architecture documentation
docs/             # User guides and tutorials
```

## Running Tests

```bash
# Full suite
uv run pytest tests/ -v

# Specific module
uv run pytest tests/test_state.py -v

# With coverage output
uv run pytest tests/ -v --tb=short
```

All 1055 tests should pass. If any fail on a fresh clone, please open an issue.

## Code Style

- **Linter:** ruff (line-length 100, target py311)
- **Type hints** on all function signatures
- **Imports:** stdlib, then third-party, then local (sorted by ruff)
- **No external dependencies** in `scripts/` — stdlib only. This is a hard rule.

```bash
# Lint
uv run ruff check scripts/ tests/

# Format
uv run ruff format scripts/ tests/
```

## Making Changes

### 1. Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming: `feature/`, `fix/`, `refactor/`, `docs/`

### 2. Write Tests First

Every change needs tests. Write them before the implementation:

```bash
# Create or modify test file
uv run pytest tests/test_your_module.py -v  # Should fail (red)

# Implement
uv run pytest tests/test_your_module.py -v  # Should pass (green)

# Full suite to check for regressions
uv run pytest tests/ -q
```

### 3. Commit

Commit messages use imperative mood, lowercase, no period:

```
feat: add webhook support to board sync
fix: handle empty phase description in CLI provider
refactor: extract common db patterns into context manager
docs: add board integration tutorial
test: add regression tests for node repair
chore: update schema migration to v8
```

### 4. Submit PR

```bash
git push origin feature/your-feature-name
```

Open a pull request against `main`. Include:
- What changed and why
- Test plan (what tests were added/modified)
- Any breaking changes

## Architecture Notes

### Adding a New Command

1. Create `skills/your-command/SKILL.md` with the command definition
2. Add any new Python logic to `scripts/`
3. Add tests to `tests/`
4. Run `uv run python scripts/generate_commands.py` to regenerate wrappers
5. Update `docs/command-reference.md`

### Adding a Board Provider

1. Create `scripts/board/your_provider.py`
2. Implement the `BoardProvider` protocol (see `scripts/board/provider.py`)
3. Call `register_provider("name", YourProvider)` at module level
4. Import your module in `scripts/board/sync.py` to trigger registration
5. Add tests to `tests/`

### Database Schema Changes

1. Add migration function `_migrate_vN_to_vN+1()` in `scripts/db.py`
2. Update `_run_migrations()` to call it
3. Update `_init_schema()` for fresh databases
4. Add migration tests to `tests/test_board_migration.py` (or new test file)
5. Document in CHANGELOG.md

## Design Principles

1. **Stdlib only** — No external dependencies in production code
2. **SQLite as source of truth** — All state in the database, never in files
3. **Deterministic behavior** — Same state = same output, always
4. **Graceful degradation** — Every integration fails silently (Nero, board sync, MCP)
5. **Quality by default** — Gates and review are automatic, not opt-in

## Questions?

Open an issue on [GitHub](https://github.com/mattjaikaran/meridian/issues).
