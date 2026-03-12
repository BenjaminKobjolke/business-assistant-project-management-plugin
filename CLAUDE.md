# Business Assistant - Project Management Plugin

## Commands

- `uv sync --all-extras` — Install dependencies
- `uv run pytest tests/ -v` — Run all tests
- `uv run ruff check src/ tests/` — Lint
- `uv run mypy src/` — Type check

## Architecture

- `config.py` — PmSettings frozen dataclass (db_path only)
- `constants.py` — All string constants, env vars, system prompt
- `database.py` — SQLAlchemy models + PmDatabase CRUD
- `tracking_service.py` — Email-task tracking operations
- `project_service.py` — Project/synonym CRUD + RTM tag extraction
- `delegation_service.py` — Delegation email composition
- `plugin.py` — register() + 17 PydanticAI tool definitions

## Database

SQLite at `data/pm.db` with tables:
- `pm_settings` — Runtime key-value configuration
- `pm_projects` — Projects with RTM tags and Obsidian links
- `pm_project_synonyms` — Case-insensitive project aliases
- `pm_contacts` — Delegation contacts with RTM list tags
- `pm_tracking` — Email-task tracking records

## Cross-Plugin Dependencies

Accesses other plugin services via `ctx.deps.plugin_data`:
- `rtm_service` — RTM task operations (from RTM plugin)
- `email_service` — Email operations (from IMAP plugin)
- `obsidian_service` — Note operations (from Obsidian plugin)

## Rules

- Use objects for related values (DTOs/Settings/Config)
- Centralize string constants in `constants.py`
- Tests are mandatory — use pytest with `spec=` on MagicMock
- DRY — no code duplication
- `pyproject.toml` is the single source of truth
- Frozen dataclasses for settings
- Type hints on all public APIs
- Tests must be fast and isolated (no network, in-memory SQLite)
