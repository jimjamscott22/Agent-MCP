# MCP Agents Registry

`mcp-agents-registry` is a local MCP server in Python that discovers `AGENTS.md` and `agents.md` files across explicitly whitelisted roots, builds a searchable registry, and resolves the effective inherited agent context for any path inside those roots.

It is designed for coding-agent workflows where project-local instruction files exist at workspace, repository, and subproject levels.

## What It Does

- Scans one or more configured roots for `AGENTS.md` / `agents.md`
- Ignores junk directories such as `.git`, `node_modules`, `.venv`, `dist`, `build`, and `__pycache__`
- Stores raw markdown plus structured parsed sections
- Builds stable project records with parent/child relationships
- Resolves effective inherited context for arbitrary paths
- Exposes registry data through MCP tools and read-only MCP resources
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
│   └── utils.py
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
```

Notes:

- Roots are mandatory and must already exist.
- The server never scans outside configured roots.
- Symlinks are not followed unless `follow_symlinks` is enabled.
- If `cache_path` is omitted, the cache defaults to `.cache/agents_registry_cache.json` relative to the config file.

## How Scanning Works

Each discovered `AGENTS.md` creates one project record.

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

## MCP Tools

- `list_projects`: return all indexed projects with metadata
- `get_project(project_name)`: return one project, raw markdown, parsed sections, and relationships
- `resolve_context(path)`: return effective merged context, matched files, and resolution trace
- `search_projects(query)`: search names, paths, tags, summaries, and raw markdown
- `refresh_index()`: rescan and report added, changed, and removed projects

## MCP Resources

- `agents://projects`
- `agents://project/{project_name}`
- `agents://project/{project_name}/raw`
- `agents://project/{project_name}/effective`
- `agents://path/{encoded_path}`

Resources return read-only JSON payloads, except the `/raw` resource which returns the raw markdown content.

## Local Development

Install dependencies:

```bash
python3 -m pip install -e .
```

Prepare config:

```bash
cp config.yaml.example config.yaml
```

Run the server over stdio:

```bash
AGENTS_REGISTRY_CONFIG=config.yaml python3 server.py
```

Or use the console entry point:

```bash
AGENTS_REGISTRY_CONFIG=config.yaml mcp-agents-registry
```

## Testing

Run the unit test suite:

```bash
python3 -m unittest discover -s tests -v
```

## Assumptions

- The implementation targets the current `mcp.server.fastmcp.FastMCP` SDK style.
- MCP resources are returned as JSON strings for compatibility with read-only resource handlers.
- Section conflict resolution is deterministic and explicit, but still heuristic for freeform markdown content.
