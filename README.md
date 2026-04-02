# MCP Agents Registry

`mcp-agents-registry` is a local MCP server in Python that discovers `AGENTS.md`, `agents.md`, `CLAUDE.md`, and `claude.md` files across explicitly whitelisted roots, builds a searchable registry, resolves effective inherited context for any path inside those roots, and provides inventory management for coding agents/accounts/devices/skills.

It is designed for coding-agent workflows where project-local instruction files exist at workspace, repository, and subproject levels.

## What It Does

- Scans one or more configured roots for `AGENTS.md` / `agents.md` / `CLAUDE.md` / `claude.md`
- Ignores junk directories such as `.git`, `node_modules`, `.venv`, `dist`, `build`, and `__pycache__`
- Stores raw markdown plus structured parsed sections
- Builds stable project records with parent/child relationships
- Resolves effective inherited context for arbitrary paths
- Exposes registry data through MCP tools and read-only MCP resources
- Tracks inventory of accounts/devices/installed agents/skills
- Supports safe read/edit operations for AGENTS/CLAUDE markdown files
- Caches parsed results to avoid unnecessary reparsing of unchanged files

## Why It Is Useful

Many codebases have layered agent instructions. A workspace root may define global rules, a repository may define build and architecture guidance, and a subproject may override implementation details. This server turns those files into a consistent, debuggable registry and makes context resolution explicit.

## Project Layout

```text
.
├── config.yaml.example
├── LICENSE
├── mcp_agents_registry/
│   ├── __init__.py
│   ├── cache.py
│   ├── config.py
│   ├── models.py
│   ├── parser.py
│   ├── prompts.py
│   ├── registry.py
│   ├── resolver.py
│   ├── resources.py
│   ├── scanner.py
│   ├── server.py
│   ├── utils.py
│   ├── web.py
│   └── web_assets/
│       ├── static/
│       │   ├── app.js
│       │   └── styles.css
│       └── templates/
│           └── admin.html
├── pyproject.toml
├── README.md
├── server.py
└── tests/
    ├── test_parser.py
    ├── test_registry.py
    └── test_scanner.py
```

## Configuration

Create a `config.yaml` based on the example file:

```yaml
roots:
  - /home/jamie/Projects
  - /home/jamie/School
  - /home/jamie/Homelab

agent_filenames:
  - AGENTS.md
  - agents.md
  - CLAUDE.md
  - claude.md

ignore_dirs:
  - .git
  - node_modules
  - .venv
  - dist
  - build
  - __pycache__

merge_mode: hierarchy
cache_enabled: true
parse_sections: true
follow_symlinks: false
inventory_path: .cache/agents_inventory.json
```

Notes:

- Roots are mandatory and must already exist.
- The server never scans outside configured roots.
- Symlinks are not followed unless `follow_symlinks` is enabled.
- If `cache_path` is omitted, the cache defaults to `.cache/agents_registry_cache.json` relative to the config file.

## How Scanning Works

Each discovered `AGENTS.md`/`CLAUDE.md` file creates one project record.

Each record includes:

- `project_name`
- `agent_file_path`
- `project_root`
- `relative_root_from_scan_base`
- `parent_project_name`
- `depth`
- `raw_markdown`
- `parsed_sections`
- `tags`
- `summary`
- `mtime`
- `sha256`

Project names default to the directory containing the agent file. Duplicate names are disambiguated with a relative path suffix.

## How Inheritance Works

When resolving a target path, the server gathers every matching project whose root is an ancestor of the target path, ordered from broadest to narrowest.

Example:

```text
/home/user/Projects/AGENTS.md
/home/user/Projects/LastSeen/AGENTS.md
/home/user/Projects/LastSeen/frontend/AGENTS.md
```

Resolving:

```text
/home/user/Projects/LastSeen/frontend/src/App.tsx
```

Produces matches in this order:

1. `/home/user/Projects/AGENTS.md`
2. `/home/user/Projects/LastSeen/AGENTS.md`
3. `/home/user/Projects/LastSeen/frontend/AGENTS.md`

Merge defaults:

- `purpose` and `overview`: nearest non-empty value wins
- `commands`: combined and deduplicated
- `constraints`: combined and deduplicated
- `coding_rules`: keyed merge with nearest value replacing broader conflicts
- `testing`: combined and deduplicated with narrower rules appearing later
- `architecture`: combined and deduplicated
- `definition_of_done`: keyed merge with narrower rules replacing broader conflicts
- `raw_combined_markdown`: concatenated in inheritance order with source markers

## Parsed Sections

The parser extracts common headings when present:

- Purpose
- Overview
- Stack
- Commands
- Setup
- Constraints
- Coding Rules
- Testing
- Architecture
- Definition of Done
- Notes

Missing sections are allowed. Raw markdown is always retained.

## Inventory Management

The server includes a persistent inventory store (JSON with schema versioning) to track:

- Accounts
- Devices
- Agent installations on account/device pairs
- Skills per installation

This data is separate from scan cache and defaults to:

```text
.cache/agents_inventory.json
```

### Example inventory workflows

- Create account/device records
- Assign an agent + skills to an account/device pair
- Query where a specific agent is installed
- Query effective skills on an account/device
- Generate coverage reports (unassigned devices, unused accounts, skill totals)

## Managed File Editing

The server supports safe read/edit operations for managed markdown files:

- `AGENTS.md` / `agents.md`
- `CLAUDE.md` / `claude.md`

Safety rules:

- File path must be inside configured roots
- Unsupported filenames are rejected
- Writes are atomic
- Optional optimistic concurrency via `expected_sha256`
- Section-aware updates are supported via heading upsert

## Getting Started

### 1. Install

```bash
python3 -m pip install -e .
```

### 2. Configure

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` to point `roots` at the directories you want scanned. Every directory listed must already exist. The server will recursively find all `AGENTS.md` and `agents.md` files under those roots.

### 3. Connect to an MCP Client

The server communicates over stdio using the MCP protocol. You can connect it to any MCP-compatible client.

**Claude Desktop** — add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agents-registry": {
      "command": "mcp-agents-registry",
      "env": {
        "AGENTS_REGISTRY_CONFIG": "/absolute/path/to/config.yaml"
      }
    }
  }
}
```

**Claude Code** — add this to your `.claude/settings.json` or run `claude mcp add`:

```json
{
  "mcpServers": {
    "agents-registry": {
      "command": "mcp-agents-registry",
      "env": {
        "AGENTS_REGISTRY_CONFIG": "/absolute/path/to/config.yaml"
      }
    }
  }
}
```

**Run manually** (for testing):

```bash
AGENTS_REGISTRY_CONFIG=config.yaml python3 server.py
```

## Usage

Once connected, the server exposes registry + inventory + managed-file tools.

### `list_projects`

Returns every indexed project with its name, root path, tags, summary, and parent/child relationships.

Use this to get an overview of all discovered `AGENTS.md` files across your configured roots.

### `get_project(project_name)`

Returns full details for a single project — raw markdown, parsed sections, tags, and relationships.

Example: `get_project("frontend")` returns the parsed content of the `AGENTS.md` found in a directory named `frontend`.

### `resolve_context(path)`

The core tool. Given any file or directory path, returns the **effective merged context** by combining all `AGENTS.md` files from ancestor directories. The response includes:

- The merged sections (purpose, commands, coding rules, etc.)
- A resolution trace showing which files matched and how conflicts were resolved

Example: calling `resolve_context("/home/user/Projects/LastSeen/frontend/src/App.tsx")` would merge instructions from:

1. `/home/user/Projects/AGENTS.md` (broadest)
2. `/home/user/Projects/LastSeen/AGENTS.md`
3. `/home/user/Projects/LastSeen/frontend/AGENTS.md` (nearest, highest priority)

### `search_projects(query)`

Full-text search across project names, paths, tags, summaries, and raw markdown. Results are ranked by relevance.

Example: `search_projects("react testing")` finds projects mentioning React and testing.

### `refresh_index()`

Rescans all configured roots and reports how many projects were added, changed, or removed since the last scan. Call this after creating or editing `AGENTS.md` files.

### Inventory tools

- `list_accounts`, `create_account`, `update_account`, `delete_account`
- `list_devices`, `create_device`, `update_device`, `delete_device`
- `list_installations`, `assign_agent_installation`, `remove_agent_installation`
- `where_is_agent_installed`, `skills_for_account_device`
- `inventory_coverage`, `search_inventory`

### Managed file tools

- `list_managed_files(path_query?)`
- `read_managed_file(path)`
- `update_managed_file(path, content, expected_sha256?)`
- `update_managed_file_section(path, section_heading, section_content, expected_sha256?)`

## Admin Web UI

The project now includes an optional local admin web interface for common operational tasks.

### Install web dependencies

```bash
python3 -m pip install -e .[web]
```

### Run the admin UI

```bash
AGENTS_REGISTRY_CONFIG=config.yaml mcp-agents-registry-web
```

Optional flags:

```bash
mcp-agents-registry-web --host 127.0.0.1 --port 8765 --config config.yaml
```

Then open:

```text
http://127.0.0.1:8765
```

### Development workflow (local iteration)

From the repository root, this single PowerShell command will sync deps, start the admin server, and open the UI in your browser:

```powershell
uv sync; $env:AGENTS_REGISTRY_CONFIG = "config.yaml"; Start-Process "http://127.0.0.1:8765"; uv run mcp-agents-registry-web --host 127.0.0.1 --port 8765
```

Stop the server with `Ctrl+C` in the same terminal when done.

### Admin endpoints

The UI uses these HTTP endpoints:

- `GET /api/health`
- `GET /api/projects`
- `GET /api/projects/{project_name}`
- `GET /api/projects/{project_name}/effective`
- `GET /api/search?query=...`
- `GET /api/context?path=...`
- `POST /api/refresh`
- `GET /api/accounts`
- `POST /api/accounts`
- `PATCH /api/accounts/{account_id}`
- `DELETE /api/accounts/{account_id}`
- `GET /api/devices`
- `POST /api/devices`
- `PATCH /api/devices/{device_id}`
- `DELETE /api/devices/{device_id}`
- `GET /api/installations`
- `POST /api/installations`
- `DELETE /api/installations`
- `GET /api/inventory/coverage`
- `GET /api/inventory/search`
- `GET /api/inventory/where-agent`
- `GET /api/inventory/skills`
- `GET /api/files`
- `GET /api/files/read`
- `PUT /api/files/write`
- `PUT /api/files/write-section`

### UI implementation notes

- The admin UI backend is implemented in `mcp_agents_registry/web.py`.
- The page template is loaded from `mcp_agents_registry/web_assets/templates/admin.html`.
- Frontend code is split into static files served at `/static`:
  - `mcp_agents_registry/web_assets/static/styles.css`
  - `mcp_agents_registry/web_assets/static/app.js`
- The admin API layer reuses `AgentsRegistry` directly to keep MCP and web behavior consistent.

## MCP Resources

Resources provide read-only access to registry data via URI:

| URI                                    | Returns                                |
| -------------------------------------- | -------------------------------------- |
| `agents://projects` | Full project index as JSON |
| `agents://project/{name}` | Single project record as JSON |
| `agents://project/{name}/raw` | Raw markdown content |
| `agents://project/{name}/effective` | Resolved context for the project root |
| `agents://path/{encoded_path}` | Resolved context for any file path |
| `agents://inventory` | Full inventory snapshot + coverage |
| `agents://inventory/account/{account_id}` | Inventory installations for one account |
| `agents://inventory/device/{device_id}` | Inventory installations for one device |
| `agents://managed-files` | Managed AGENTS/CLAUDE files snapshot |

## Testing

Run the unit test suite:

```bash
python3 -m pytest tests/ -v
```

Or with unittest:

```bash
python3 -m unittest discover -s tests -v
```

## Assumptions

- The implementation targets the current `mcp.server.fastmcp.FastMCP` SDK style.
- MCP resources are returned as JSON strings for compatibility with read-only resource handlers.
- Section conflict resolution is deterministic and explicit, but still heuristic for freeform markdown content.
