# Codex Prompt — Build an MCP Agents Registry Server (Option B)

## Objective

Build a **local MCP server** in **Python** that discovers, indexes, resolves, and serves `AGENTS.md` / `agents.md` files across multiple project roots.

This server should act as a **project context registry** for coding agents. Its job is to connect project-local agent instruction files to the correct repositories, subprojects, and file paths, then expose that information through **MCP tools** and **MCP resources**.

The implementation should be clean, production-minded, extensible, and easy to run locally.

---

## Product Goal

I want a local MCP server that:

- scans one or more configured root directories
- finds every `AGENTS.md` or `agents.md`
- treats each discovered file as a project or subproject instruction source
- builds a searchable registry of projects
- resolves the effective agent context for any given file or folder path
- supports hierarchical inheritance from parent `AGENTS.md` files
- exposes project data through MCP **tools**
- exposes read-only project context through MCP **resources**
- keeps both **raw markdown** and **structured parsed content**
- supports caching and refresh behavior
- is safe by default by only scanning explicitly whitelisted roots

This should be **Option B** architecture: a real registry server, not just a nearest-file lookup script.

---

## Technical Constraints

- Language: **Python**
- Use the **MCP Python SDK**
- Code should be modular and split across multiple files
- Type hints should be used throughout
- Avoid unnecessary framework bloat
- Favor simple standard-library solutions where reasonable
- The server should run locally over stdio first
- Make the filesystem scanner efficient and safe
- Ignore junk directories like `.git`, `node_modules`, `.venv`, `dist`, `build`, and `__pycache__`

---

## High-Level Architecture

Implement the project with these modules:

```text
mcp-agents-registry/
├── server.py
├── config.py
├── models.py
├── scanner.py
├── parser.py
├── resolver.py
├── cache.py
├── resources.py
├── prompts.py
├── utils.py
├── config.yaml.example
├── README.md
├── pyproject.toml
└── tests/
```

### Responsibilities

#### `server.py`
- bootstraps the MCP server
- registers tools
- registers resources
- wires dependencies together

#### `config.py`
- loads YAML config
- validates root directories
- validates supported filenames
- exposes runtime settings

#### `models.py`
Define data models for:
- project records
- parsed agent sections
- resolution traces
- effective context results
- cache records

Use dataclasses or Pydantic only if truly helpful. Prefer lightweight structures.

#### `scanner.py`
- recursively scans configured roots
- finds valid `AGENTS.md` / `agents.md`
- skips ignored directories
- determines probable project roots
- computes file metadata like:
  - absolute path
  - project root
  - file size
  - last modified time
  - content hash

#### `parser.py`
- reads raw markdown
- extracts common sections if present
- stores both raw and structured content

Structured section extraction should try to detect headings such as:
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

Do not fail if sections are missing. Return partial structured output safely.

#### `resolver.py`
Given a target path:
- identify the applicable project/subproject entries
- find the nearest matching `AGENTS.md`
- collect parent agent files up the directory chain within allowed roots
- merge contexts according to precedence rules
- return:
  - effective merged context
  - list of matched files
  - resolution trace
  - structured merged sections
  - raw combined markdown

#### `cache.py`
- persist scan results locally
- support lightweight refresh logic
- use content hash and modified time to avoid unnecessary reparsing

#### `resources.py`
- define MCP resource handlers
- expose read-only views of indexed data

#### `prompts.py`
- define useful prompt templates for clients if supported
- optional but should be included

#### `tests/`
Add unit tests for:
- scanner behavior
- parser section extraction
- resolver precedence
- path-to-project resolution
- ignored directories behavior

---

## Required MCP Tools

Implement at least these MCP tools.

### 1. `list_projects`
Return all indexed projects with metadata.

Output fields should include:
- project name
- project root
- agent file path
- parent project if any
- tags
- summary
- last modified

### 2. `get_project`
Input:
- `project_name`

Return:
- metadata for the selected project
- raw agent file content
- parsed sections
- parent/child relationships if known

### 3. `resolve_context`
Input:
- `path`

Return:
- the effective instructions that apply to that path
- matched agent files from broadest to narrowest
- the final merged result
- a resolution trace that explains how the answer was determined

This is the most important tool.

### 4. `search_projects`
Input:
- `query`

Search across:
- project name
- path
- tags
- summary
- raw markdown text

Return ranked matches.

### 5. `refresh_index`
Trigger a rescan and rebuild or update the registry cache.

Return:
- number of projects found
- number added
- number changed
- number removed

---

## Required MCP Resources

Implement these read-only resources if supported cleanly by the SDK.

### Resource URIs

- `agents://projects`
  - returns the full registry index

- `agents://project/{project_name}`
  - returns a single project record

- `agents://project/{project_name}/raw`
  - returns raw markdown for that project

- `agents://project/{project_name}/effective`
  - returns the effective context for that project root

- `agents://path/{encoded_path}`
  - resolves effective context for an arbitrary path

If SDK ergonomics differ, adapt while preserving equivalent functionality.

---

## Merge and Inheritance Rules

This system must support hierarchical inheritance.

### Example

```text
/home/user/Projects/AGENTS.md
/home/user/Projects/LastSeen/AGENTS.md
/home/user/Projects/LastSeen/backend/AGENTS.md
```

For a target path like:

```text
/home/user/Projects/LastSeen/backend/routes/users.py
```

the server should gather applicable files in this order:

1. `/home/user/Projects/AGENTS.md`
2. `/home/user/Projects/LastSeen/AGENTS.md`
3. `/home/user/Projects/LastSeen/backend/AGENTS.md`

Then merge them with **nearest file taking precedence**.

### Merge behavior

Use these defaults:

- `purpose` / `overview`:
  - nearest overrides broader parent

- `commands`:
  - combine and deduplicate

- `constraints`:
  - combine and deduplicate

- `coding rules`:
  - nearest overrides conflicting broader rules

- `testing rules`:
  - combine, nearest displayed last

- `architecture notes`:
  - combine

- `definition of done`:
  - nearest overrides, but retain inherited notes when non-conflicting

Also return the raw combined markdown in inheritance order.

---

## Project Discovery Rules

A discovered `AGENTS.md` should create a registry record.

Each record should include:

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

### Naming rules

Project names should be stable and human-readable.

Suggested logic:
- default to the directory name containing the `AGENTS.md`
- if duplicate names exist, disambiguate with a relative path suffix
- preserve exact path internally

---

## Configuration File

Create a YAML config file example like this:

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

The app should validate config and fail clearly on invalid roots.

---

## Safety Requirements

- Never scan outside configured roots
- Do not follow symlinks unless explicitly enabled
- Normalize and validate all paths before use
- Ensure a request for `resolve_context(path)` cannot escape allowed roots via path traversal
- Handle unreadable files gracefully
- Return useful errors, not stack-trace soup

---

## Performance Expectations

- Use cached metadata to avoid reparsing unchanged files
- Avoid loading unnecessary files repeatedly
- Scanner should skip ignored directories efficiently
- Registry rebuilds should be incremental when practical
- Keep implementation simple and maintainable over being prematurely clever

---

## CLI / Local Development Expectations

Provide a clean local developer workflow.

### Deliverables
- `pyproject.toml`
- install/run instructions in `README.md`
- example config file
- tests
- clear entry point

### README should include
- what the server does
- why it is useful
- config setup
- how scanning works
- how inheritance works
- available tools and resources
- how to run locally
- how to test

---

## Output Quality Expectations

The code should be:

- well-organized
- readable
- commented where helpful
- typed
- easy to extend

Do not generate fake placeholder architecture. Implement real working logic.

If some MCP SDK APIs differ from my assumptions, adapt to the current SDK while preserving the intended functionality.

---

## Acceptance Criteria

The build is successful only if all of the following are true:

1. The server runs locally with the MCP Python SDK.
2. It scans multiple configured roots and finds `AGENTS.md` files.
3. It ignores directories like `.git`, `node_modules`, and `.venv`.
4. It stores both raw markdown and parsed sections.
5. It can list indexed projects.
6. It can retrieve one project by name.
7. It can search projects.
8. It can resolve effective context for an arbitrary path.
9. It merges parent and child `AGENTS.md` files with nearest precedence.
10. It returns a useful resolution trace.
11. It supports refresh behavior.
12. It includes tests for core resolution logic.
13. It includes a solid README and config example.

---

## Example Scenario to Support

Given:

```text
/home/jamie/Projects/AGENTS.md
/home/jamie/Projects/LastSeen/AGENTS.md
/home/jamie/Projects/LastSeen/frontend/AGENTS.md
/home/jamie/Projects/ThreatStream-lite/AGENTS.md
```

Then:

### `list_projects`
should show at least:
- Projects
- LastSeen
- frontend
- ThreatStream-lite

### `resolve_context("/home/jamie/Projects/LastSeen/frontend/src/App.tsx")`
should:
- match the workspace root `AGENTS.md`
- match the repo-level `LastSeen/AGENTS.md`
- match the frontend `AGENTS.md`
- merge them in that order
- return frontend instructions as highest precedence

---

## Implementation Notes

- Prefer deterministic behavior
- Prefer explicit merge rules over vague heuristics
- Prefer robust path normalization
- Prefer returning structured JSON-friendly outputs from tools
- Keep raw markdown available for debugging and advanced clients
- Include a clear resolution trace because debugging context selection is essential

---

## Final Instruction

Build the project as a real, working Python MCP server scaffold with actual implementation, not just pseudocode.

Return:
1. the complete project file tree
2. the contents of each file
3. setup instructions
4. any assumptions you had to make

If needed, make reasonable implementation choices and document them clearly.
