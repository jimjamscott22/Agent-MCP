# Agent-MCP Knowledge Graph

## Overview

This document captures a knowledge-graph-style view of the `jimjamscott22/Agent-MCP` repository based on the uploaded repository documents:

- `codex_prompt_mcp_agents_registry.md`
- `README.md`
- `CLAUDE.md`

The repository describes a **local Python MCP server** that discovers agent instruction files such as `AGENTS.md` and `CLAUDE.md`, builds a searchable registry, resolves inherited context for arbitrary paths, and exposes the results through **MCP tools**, **MCP resources**, and an optional **admin web UI**.

## Source Basis

This graph was derived from:

- Codex build specification describing the intended architecture and acceptance criteria
- Repository README describing the implemented project layout, features, tools, resources, admin UI, and workflows
- `CLAUDE.md` describing architecture, commands, module responsibilities, and resolution behavior

---

## High-Level System Graph

```mermaid
graph TD
    A[mcp-agents-registry] --> B[MCP Python SDK]
    A --> C[server.py]
    A --> D[config.py]
    A --> E[models.py]
    A --> F[scanner.py]
    A --> G[parser.py]
    A --> H[registry.py]
    A --> I[resolver.py]
    A --> J[cache.py]
    A --> K[resources.py]
    A --> L[prompts.py]
    A --> M[Admin Web UI]

    D --> D1[YAML config]
    D1 --> D2[roots]
    D1 --> D3[agent_filenames]
    D1 --> D4[ignore_dirs]
    D1 --> D5[merge_mode hierarchy]
    D1 --> D6[cache_enabled]
    D1 --> D7[follow_symlinks]

    F --> N[Agent files]
    N --> N1[AGENTS.md]
    N --> N2[agents.md]
    N --> N3[CLAUDE.md]
    N --> N4[claude.md]
    F --> O[Ignored directories]

    G --> P[Parsed sections]
    G --> Q[Raw markdown]

    H --> R[Project records]
    H --> S[Search ranking]
    H --> I

    I --> T[Hierarchical inheritance]
    I --> U[Effective context]
    I --> V[Resolution trace]

    C --> W[list_projects]
    C --> X[get_project]
    C --> Y[resolve_context]
    C --> Z[search_projects]
    C --> AA[refresh_index]

    C --> AB[agents://projects]
    C --> AC[agents://project/{name}]
    C --> AD[agents://project/{name}/raw]
    C --> AE[agents://project/{name}/effective]
    C --> AF[agents://path/{encoded_path}]

    J --> R
    K --> AB
    K --> AC
    K --> AD
    K --> AE
    K --> AF

    M --> AG[Admin API]
    M --> H
    M --> AH[Managed markdown files]
    A --> AI[Inventory system]
    M --> AI

    A --> AJ[Safety guardrails]
    AJ --> F
    AJ --> I
    AJ --> AH

    A --> AK[Test suite]
    AK --> F
    AK --> G
    AK --> H
    AK --> I
```

---

## Core Pipeline

The repository architecture can be summarized as:

**scan → parse → cache → registry → resolve → serve**

### Pipeline stages

1. **Scan**
   - `scanner.py` recursively walks configured roots
   - finds supported instruction files:
     - `AGENTS.md`
     - `agents.md`
     - `CLAUDE.md`
     - `claude.md`
   - skips ignored directories like:
     - `.git`
     - `node_modules`
     - `.venv`
     - `dist`
     - `build`
     - `__pycache__`

2. **Parse**
   - `parser.py` reads markdown
   - extracts structured sections such as:
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
   - preserves full raw markdown

3. **Cache**
   - `cache.py` stores scan and parse results
   - uses metadata like:
     - modification time
     - size
     - SHA-256 hash
   - avoids reparsing unchanged files

4. **Registry**
   - `registry.py` stores project records
   - manages parent and child relationships
   - supports refresh and weighted search

5. **Resolve**
   - `resolver.py` determines which instruction files apply to a given path
   - merges inherited context from broadest to narrowest
   - produces:
     - effective context
     - matched files
     - merged sections
     - raw combined markdown
     - resolution trace

6. **Serve**
   - `server.py` exposes MCP tools and resources
   - optional web layer exposes admin HTTP routes

---

## Module Graph

### `server.py`
**Role:** bootstraps the MCP server and registers interfaces.

**Connected to:**
- `registry.py`
- `resolver.py`
- `resources.py`
- `prompts.py`

**Registers tools:**
- `list_projects`
- `get_project`
- `resolve_context`
- `search_projects`
- `refresh_index`

**Registers resources:**
- `agents://projects`
- `agents://project/{name}`
- `agents://project/{name}/raw`
- `agents://project/{name}/effective`
- `agents://path/{encoded_path}`

---

### `config.py`
**Role:** loads and validates YAML configuration.

**Key responsibilities:**
- validate configured roots
- validate supported filenames
- expose runtime settings
- control cache and symlink behavior

**Depends on:**
- YAML config
- root safety rules

---

### `models.py`
**Role:** defines structured data entities.

**Primary concepts:**
- project records
- parsed agent content
- effective context
- resolution trace/steps
- refresh summaries
- cache records

---

### `scanner.py`
**Role:** scans configured filesystem roots.

**Produces:**
- discovered instruction-file records
- metadata:
  - absolute path
  - project root
  - size
  - mtime
  - SHA-256 hash

**Depends on:**
- configured roots
- supported filenames
- ignored directory rules

---

### `parser.py`
**Role:** extracts structured meaning from markdown files.

**Produces:**
- parsed sections
- raw markdown retention

**Behavior:**
- tolerant of missing sections
- partial extraction is valid
- does not fail if headings are absent

---

### `registry.py`
**Role:** central coordination layer.

**Responsibilities:**
- hold all indexed projects
- refresh the index
- manage relationships
- support weighted search
- delegate path resolution

**Important relationship:**
- `registry.py` is the main in-memory coordination point

---

### `resolver.py`
**Role:** path-aware inheritance engine.

**Responsibilities:**
- validate target paths
- find all ancestor project records
- merge files in inheritance order
- apply nearest-precedence logic
- produce resolution trace

**This is the heart of the project.**

---

### `cache.py`
**Role:** persistence for unchanged scan/parse state.

**Benefits:**
- faster refreshes
- fewer unnecessary parses
- stable metadata-based invalidation

---

### `resources.py`
**Role:** generate read-only resource payloads.

**Purpose:**
- expose registry data to MCP clients through resource URIs

---

### `prompts.py`
**Role:** optional prompt templates.

**Purpose:**
- provide reusable prompt scaffolding for clients that support prompts

---

### `web.py` / Admin Web UI
**Role:** optional FastAPI-based operational surface.

**Responsibilities:**
- serve browser-based admin interface
- expose project and inventory APIs
- reuse the same `AgentsRegistry` behavior as the MCP server

---

## Knowledge Graph: Nodes and Edges

### Nodes

```json
{
  "nodes": [
    {"id":"mcp-agents-registry","type":"project"},
    {"id":"MCP Python SDK","type":"technology"},
    {"id":"server.py","type":"module"},
    {"id":"config.py","type":"module"},
    {"id":"models.py","type":"module"},
    {"id":"scanner.py","type":"module"},
    {"id":"parser.py","type":"module"},
    {"id":"registry.py","type":"module"},
    {"id":"resolver.py","type":"module"},
    {"id":"cache.py","type":"module"},
    {"id":"resources.py","type":"module"},
    {"id":"prompts.py","type":"module"},
    {"id":"Admin Web UI","type":"component"},
    {"id":"YAML config","type":"config"},
    {"id":"Agent files","type":"concept"},
    {"id":"Parsed sections","type":"concept"},
    {"id":"Raw markdown","type":"concept"},
    {"id":"Project records","type":"concept"},
    {"id":"Hierarchical inheritance","type":"concept"},
    {"id":"Effective context","type":"concept"},
    {"id":"Resolution trace","type":"concept"},
    {"id":"Search ranking","type":"logic"},
    {"id":"Safety guardrails","type":"security"},
    {"id":"Inventory system","type":"feature"},
    {"id":"Managed markdown files","type":"feature"},
    {"id":"Test suite","type":"quality"},
    {"id":"list_projects","type":"tool"},
    {"id":"get_project","type":"tool"},
    {"id":"resolve_context","type":"tool"},
    {"id":"search_projects","type":"tool"},
    {"id":"refresh_index","type":"tool"},
    {"id":"agents://projects","type":"resource"},
    {"id":"agents://project/{name}","type":"resource"},
    {"id":"agents://project/{name}/raw","type":"resource"},
    {"id":"agents://project/{name}/effective","type":"resource"},
    {"id":"agents://path/{encoded_path}","type":"resource"}
  ]
}
```

### Edges

```json
{
  "edges": [
    {"from":"mcp-agents-registry","to":"MCP Python SDK","type":"uses"},
    {"from":"mcp-agents-registry","to":"server.py","type":"bootstraps_with"},
    {"from":"mcp-agents-registry","to":"config.py","type":"configured_by"},
    {"from":"mcp-agents-registry","to":"models.py","type":"modeled_by"},
    {"from":"mcp-agents-registry","to":"scanner.py","type":"discovers_with"},
    {"from":"mcp-agents-registry","to":"parser.py","type":"parses_with"},
    {"from":"mcp-agents-registry","to":"registry.py","type":"indexes_with"},
    {"from":"mcp-agents-registry","to":"resolver.py","type":"resolves_with"},
    {"from":"mcp-agents-registry","to":"cache.py","type":"caches_with"},
    {"from":"mcp-agents-registry","to":"resources.py","type":"exposes_with"},
    {"from":"mcp-agents-registry","to":"prompts.py","type":"augmented_by"},
    {"from":"mcp-agents-registry","to":"Admin Web UI","type":"optionally_served_by"},
    {"from":"config.py","to":"YAML config","type":"loads"},
    {"from":"scanner.py","to":"Agent files","type":"finds"},
    {"from":"parser.py","to":"Parsed sections","type":"extracts"},
    {"from":"parser.py","to":"Raw markdown","type":"preserves"},
    {"from":"registry.py","to":"Project records","type":"stores"},
    {"from":"registry.py","to":"Search ranking","type":"implements"},
    {"from":"registry.py","to":"resolver.py","type":"delegates_to"},
    {"from":"resolver.py","to":"Hierarchical inheritance","type":"applies"},
    {"from":"resolver.py","to":"Effective context","type":"produces"},
    {"from":"resolver.py","to":"Resolution trace","type":"produces"},
    {"from":"server.py","to":"list_projects","type":"registers"},
    {"from":"server.py","to":"get_project","type":"registers"},
    {"from":"server.py","to":"resolve_context","type":"registers"},
    {"from":"server.py","to":"search_projects","type":"registers"},
    {"from":"server.py","to":"refresh_index","type":"registers"},
    {"from":"server.py","to":"agents://projects","type":"registers"},
    {"from":"server.py","to":"agents://project/{name}","type":"registers"},
    {"from":"server.py","to":"agents://project/{name}/raw","type":"registers"},
    {"from":"server.py","to":"agents://project/{name}/effective","type":"registers"},
    {"from":"server.py","to":"agents://path/{encoded_path}","type":"registers"},
    {"from":"mcp-agents-registry","to":"Safety guardrails","type":"protected_by"},
    {"from":"mcp-agents-registry","to":"Inventory system","type":"includes"},
    {"from":"mcp-agents-registry","to":"Managed markdown files","type":"manages"},
    {"from":"mcp-agents-registry","to":"Test suite","type":"validated_by"}
  ]
}
```

---

## Resolution and Inheritance Subgraph

The repo’s most important semantic engine is `resolve_context(path)`.

### Inputs
- arbitrary path inside configured roots

### Matching behavior
- collect every project record whose `project_root` is an ancestor of the target path
- sort from broadest to narrowest
- merge in that order

### Merge rules
- **purpose / overview**
  - nearest non-empty value wins
- **commands**
  - combine and deduplicate
- **constraints**
  - combine and deduplicate
- **coding rules**
  - keyed merge, nearest replaces broader conflicts
- **testing**
  - combine and deduplicate, narrower rules later
- **architecture**
  - combine and deduplicate
- **definition of done**
  - keyed merge, narrower rules replace broader conflicts
- **raw combined markdown**
  - concatenated in inheritance order with source markers

### Outputs
- effective merged context
- matched files
- merged structured sections
- raw combined markdown
- resolution trace

---

## Tool Graph

### MCP Tools
- `list_projects`
  - lists all indexed projects with metadata
- `get_project(project_name)`
  - fetches one project and its raw/parsed content
- `resolve_context(path)`
  - returns effective inherited context for a path
- `search_projects(query)`
  - weighted search over names, paths, tags, summaries, raw markdown
- `refresh_index()`
  - rescans roots and updates cache-aware registry state

### MCP Resources
- `agents://projects`
- `agents://project/{name}`
- `agents://project/{name}/raw`
- `agents://project/{name}/effective`
- `agents://path/{encoded_path}`

---

## Extended Features Graph

### Inventory system
The README indicates the repo also includes a persistent inventory model for:

- accounts
- devices
- agent installations
- skills

This makes the repo broader than a pure AGENTS resolver. It also serves as an operational registry for agent deployments.

### Managed markdown files
The project also supports safe operations for:

- listing managed AGENTS/CLAUDE files
- reading them
- atomically updating them
- section-aware updates
- optional optimistic concurrency with expected SHA-256 values

### Admin web UI
The optional FastAPI admin UI adds:
- browser access
- operational endpoints
- shared registry behavior between MCP and HTTP modes

---

## Security and Safety Graph

The repo is strongly rooted in explicit filesystem boundaries.

### Guardrails
- never scan outside configured roots
- normalize and validate all paths
- reject path traversal attempts
- do not follow symlinks unless explicitly enabled
- reject unsupported filenames
- handle unreadable files gracefully
- perform atomic writes for managed file updates

This is a very intentional design choice, and it is one of the main backbone edges in the graph.

---

## Testing Graph

The test suite validates:
- scanner behavior
- parser section extraction
- path-to-project resolution
- ignored directory handling
- nearest-precedence inheritance behavior
- registry refresh behavior

This makes the project not just “agent-y vibes in a trench coat,” but a structured, test-backed system.

---

## Plain-English Graph Summary

This repository is best understood as a **context registry and inheritance engine for coding agents**.

It does four big things:

1. **discovers** instruction files across approved roots
2. **structures** them into searchable project records
3. **resolves** which instructions apply to any given path
4. **serves** that answer through MCP, and optionally through a web admin layer

In graph form, nearly everything radiates out from:

- `registry.py`
- `resolver.py`
- `server.py`

Those three act like the project’s central nervous system.

---

## Suggested Future Additions

Potential future graph nodes that would be useful if the codebase keeps growing:

- `watcher.py` for filesystem watch mode
- `exporters.py` for Neo4j / GraphML / JSON-LD output
- `policy.py` for advanced merge policy customization
- `auth.py` if the admin UI ever needs access control
- `telemetry.py` for local-only performance metrics and debug traces

---

## Conclusion

`Agent-MCP` is not merely a nearest-file lookup utility. It is a layered, safety-conscious MCP context registry with:

- deterministic path resolution
- hierarchical inheritance
- structured parsing
- cached indexing
- searchable project metadata
- MCP tools and resources
- optional web administration
- inventory tracking
- safe markdown file management

That makes it a strong foundation for real coding-agent workflows across multiple repositories and subprojects.
