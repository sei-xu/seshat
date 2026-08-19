# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Seshat** is an archivist agent for the Seîxu ecosystem. It reads and writes markdown notes with frontmatter in the Akasha vault, transforming decisions and completed items into permanent, searchable records.

**Current Status**: Phase 3 of roadmap — all 9 core tools implemented and tested locally. Server/deploy phases (MCP, Telegram bot, git sync protocol) are future work.

## Development Setup

```bash
# Activate the virtual environment (if not already activated)
source .venv/bin/activate

# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_tools.py -v

# Run a specific test
pytest tests/test_tools.py::test_create_project -v
```

Manual smoke test (creates a real project in a temporary vault):

```bash
python3 -c "
from seshat.core import VaultClient
from seshat.core.tools import create_project, append_history

import tempfile, pathlib
root = pathlib.Path(tempfile.mkdtemp())
for f in ('01-Fragments', '02-Projects', '03-References', 'seixu'):
    (root / f).mkdir()

vault = VaultClient(root)
r = create_project(vault, year_month='202608', slug='teste', title='Teste',
                    summary='s', field='Programação', project_type='comercial')
append_history(vault, history_relative_path=f\"02-Projects/{r['slug']}/01_history.md\",
                date='2026-08-14', title='Início', summary_line='Primeira entrada.')
print((root / '02-Projects' / r['slug'] / '01_history.md').read_text())
"
```

## Architecture

### Core Layers

**`seshat/core/vault.py`** — `VaultClient`
- Thin I/O layer: reads and writes markdown files with frontmatter to disk
- Never overwrites files without explicit `overwrite=True`
- Uses the `python-frontmatter` library for parsing
- Agnostic to business logic — just knows how to serialize/deserialize notes

**`seshat/core/schema.py`** — Validation
- Enforces closed vocabulary (categories, fields, project statuses, types, etc.)
- Mirrors definitions from vault documentation (`seixu/akasha/20_frontmatter_schema.md`, `21_vocabulario_type.md`)
- Generates IDs and timestamps automatically on write
- Raises `SchemaValidationError` if frontmatter is invalid

**`seshat/core/history.py`** — History Timeline
- Parses and regenerates `01_history.md` files
- Maintains timeline (newest first in text) + Mermaid gantt chart (oldest first)
- Full regeneration on every `append_history` call

**`seshat/core/tools/`** — Business Logic (9 tools)
- Pure functions, one per file, stateless and easy to test
- **Phase 2**: `list_projects`, `get_project`, `create_project`, `append_history`, `create_fragment`
- **Phase 3**: `list_references`, `create_reference`, `update_project_status`, `search_vault`

### Test Structure

- **`conftest.py`**: Fixture `vault` creates a minimal temporary vault clone with required folders
- **`test_schema.py`**: Validation logic
- **`test_history.py`**: History file parsing and generation
- **`test_tools.py`**: Phase 2 tools
- **`test_tools_fase3.py`**: Phase 3 tools

## Key Decisions & Constraints

### Schema Sync (Upstream = Vault, Downstream = Code)

Source of truth is in the Akasha vault (`seixu/akasha/`), not this repo. Changes to vocabulary (fields, categories, types, statuses) must be replicated manually to `seshat/core/schema.py`.

Two known gaps left open by vault documentation that the code decided independently (marked with comments in `schema.py`):

- **`ai_access`**: Schema calls it "closed vocabulary" but doesn't enumerate values. Assumed `{read_write, read_only}` — update when vault formalizes.
- **`id` generation algorithm**: Schema says "auto-generate if absent" with no algorithm. Inferred pattern `<field-slug>-<category>-<slug>` from existing vault examples.

### VaultClient Behavior

- `read_note()` returns a `Note` dataclass with path, frontmatter dict, and body string
- `iter_notes()` recursively reads all `.md` files under a path; silently continues on malformed files (raises VaultError with context)
- `write_note()` validates before writing and refuses to overwrite without `overwrite=True`
- Never fabricate history — `01_history.md` is append-only (use `append_history()`, not `write_note()` with overwrite)

### Tool Design

Each tool in `seshat/core/tools/` is a stateless function. Signature pattern:

```python
def tool_name(vault: VaultClient, param1: str, param2: str, ...) -> dict:
    # Return dict with results (e.g., created object, list of items, etc.)
```

Tools validate their own inputs, call vault layer, and return structured results. Error handling is explicit — raise `VaultError` on disk I/O problems, `SchemaValidationError` on validation failures.

## Dependencies

- `python-frontmatter>=1.1` — Markdown + YAML frontmatter parsing
- `pyyaml>=6.0` — YAML parsing (used by frontmatter)
- `pytest>=8.0` (dev) — Test framework

## Next Steps (Remaining Phases)

- **Sync Protocol** (`seixu/seshat/11_git_conflitos.md`): Git sync for vault changes, conflict handling
- **HTTP/SSE Server** (`seshat/mcp/`): MCP server exposed via HTTP/SSE on Render VPS
- **Authentication**: API key validation for server
- **Telegram Bot** (`seshat/telegram/`): Chat interface to vault

## Running Tests from Claude Code

Use the `/run` skill to start the test suite, or run directly:

```bash
.venv/bin/pytest tests/ -v
```

Activate the venv first if needed:

```bash
source .venv/bin/activate
pytest tests/ -v
```

## MCP Integration (Phase 3 Complete)

The complete MCP server is ready with all 9 tools exposed via HTTP/SSE.

### Starting the MCP Server

```bash
python -m seshat.mcp.cli \
  --vault-root ./vault \
  --host localhost \
  --port 8000 \
  --api-key your-dev-key
```

Or use the installed CLI:

```bash
seshat-server --vault-root ./vault
```

### Connecting Claude to MCP

See [CLAUDE_MCP.md](CLAUDE_MCP.md) for detailed setup:
- Local development configuration
- Remote Render server integration
- Tool usage examples
- Troubleshooting guide

### Deployment

Seshat is ready for production deployment on Render or Docker:
- See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment guide
- Includes Dockerfile, render.yaml, environment setup
- Git sync integration with upstream vault
- Health checks and monitoring
