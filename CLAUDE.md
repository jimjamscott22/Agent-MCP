# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`mcp-agents-registry` is a Python MCP (Model Context Protocol) server that discovers, indexes, and resolves hierarchical `AGENTS.md`/`agents.md` files across configured root directories. It enables agents to get context-aware, inherited instructions for any path in a codebase.

## Commands

**Install (editable):**
```bash
uv sync
```

**Install with web + test extras:**
```bash
uv sync --extra dev,web
```

**Run tests:**
```bash
uv run pytest tests/ -v
# or
uv run unittest discover -s tests -v
```

**Run a single test:**
```bash
uv run pytest tests/test_registry.py::AgentsRegistryTest::test_registry_resolves_inherited_context_with_nearest_precedence -v
```

**Run the server locally:**
```bash
AGENTS_REGISTRY_CONFIG=config.yaml uv run python3 server.py
```

**After installation:**
```bash
AGENTS_REGISTRY_CONFIG=config.yaml uv run mcp-agents-registry
```

**Run the admin web UI:**
```bash
AGENTS_REGISTRY_CONFIG=config.yaml mcp-agents-registry-web
# optional
mcp-agents-registry-web --host 127.0.0.1 --port 8765 --config config.yaml
```

## Architecture

The server follows a pipeline: **scan → parse → cache → registry → resolve → serve**.

### Module Responsibilities

| Module | Role |
|--------|------|
| `server.py` (root) | Entry point; delegates to `mcp_agents_registry.server:main` |
| `mcp_agents_registry/server.py` | Creates MCP server, registers 5 tools + 5 resources + 2 prompts |
| `mcp_agents_registry/web.py` | Creates FastAPI admin server, mounts static assets, and exposes admin API routes |
| `config.py` | Loads/validates YAML config; `AppConfig` dataclass |
| `models.py` | Core dataclasses: `ProjectRecord`, `ParsedAgentContent`, `EffectiveContext`, `ResolutionStep`, `RefreshSummary` |
| `scanner.py` | Walks filesystem roots, finds agent files, computes mtime/sha256/size metadata |
| `parser.py` | Parses markdown into canonical sections (purpose, commands, constraints, etc.) |
| `registry.py` | `AgentsRegistry` — manages all projects, handles refresh, search (AND logic, weighted scores), and delegates resolution |
| `resolver.py` | `ContextResolver` — finds ancestor projects for a path and merges sections by hierarchy |
| `cache.py` | JSON cache at `.cache/agents_registry_cache.json`; validates entries by mtime + sha256 + size |
| `resources.py` | MCP resource payload generators (5 URIs under `agents://`) |
| `prompts.py` | Optional MCP prompt templates |
| `utils.py` | Path normalization, sha256 hashing, URL encoding |

### Admin Web UI Notes

- The admin page is served from `mcp_agents_registry/web_assets/templates/admin.html`.
- Frontend assets are split into:
   - `mcp_agents_registry/web_assets/static/styles.css`
   - `mcp_agents_registry/web_assets/static/app.js`
- The FastAPI app mounts `web_assets/static` at `/static`.
- Admin API routes live in `mcp_agents_registry/web.py` and intentionally reuse `AgentsRegistry` methods.

### Context Resolution Flow

When `resolve_context(path)` is called:
1. Normalize and validate the path is within configured roots
2. Find all `ProjectRecord`s whose `project_root` is an ancestor of the target path
3. Sort by depth (shallowest first)
4. Merge sections with these rules:
   - **Nearest wins:** `purpose`, `overview`
   - **Combine + deduplicate:** `stack`, `commands`, `setup`, `constraints`, `architecture`, `notes`, `testing`
   - **Keyed merge (nearest replaces):** `coding_rules`, `definition_of_done`
   - **Tags:** deduplicated, order-preserved

### MCP Interface

**5 Tools:** `list_projects`, `get_project`, `resolve_context`, `search_projects`, `refresh_index`

**5 Resources:**
- `agents://projects` — full index
- `agents://project/{name}` — single record
- `agents://project/{name}/raw` — raw markdown
- `agents://project/{name}/effective` — resolved context for project root
- `agents://path/{encoded_path}` — resolved context for any path

### Configuration

Config is loaded from `AGENTS_REGISTRY_CONFIG` env var, falling back to `./config.yaml`. See `config.yaml.example` for the full schema. Only `merge_mode: hierarchy` is supported.

### Caching

The cache (`RegistryCache`) stores parsed content keyed by file path. On `refresh_index`, only files whose mtime, sha256, or size changed are reparsed. Cache is persisted as JSON with a `version` field.

### Path Safety

All paths are normalized and validated to remain within configured roots. Symlink following is opt-in (`follow_symlinks: false` by default). Path traversal attempts are rejected by `resolve_context`.

### Search Scoring Weights

Project name: 12 · root path: 8 · agent file path: 8 · tags: 6 · summary: 5 · raw markdown: 2. All query terms must match (AND logic).
