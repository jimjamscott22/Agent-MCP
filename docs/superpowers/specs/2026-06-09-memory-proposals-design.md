# Design Spec: Human-in-the-Loop Memory Proposals

**Date:** 2026-06-09  
**Status:** Approved

## Overview

Introduce a staging layer between MCP agents and the `AGENTS.md` filesystem. Instead of writing context updates directly, agents submit *proposals* which queue in the admin UI for human review and one-click approval. The existing `update_managed_file_section()` performs the actual write — only triggered by a human approving via the web panel.

The scan→parse→cache→resolve pipeline is unchanged. This only redirects the *write* path through a human gate.

## Goals

- Agents can no longer silently edit `AGENTS.md` files by default.
- A human reviews, edits if needed, and approves/rejects in the admin UI.
- Approved proposals trigger the existing write + automatic cache invalidation (no watchdog needed — we control the write trigger).
- Direct-write tools remain available behind a config flag for advanced/script use.

## Out of Scope (Phase 2)

- Filesystem watchdog (`watchdog` library) for external write detection.
- Proposal history / audit log UI.
- Multi-user access control.

---

## 1. Data Layer — `mcp_agents_registry/proposals.py` (new file)

### Data model

Uses `@dataclass` (matching repo conventions in `models.py`; no Pydantic dependency).

```python
@dataclass
class MemoryProposal:
    id: str                   # UUID4 string
    target_project: str       # project_name from registry
    target_path: str          # Absolute path to the AGENTS.md to modify
    section_heading: str      # e.g. "Coding Rules"
    proposed_content: str     # Markdown body for the section
    rationale: str            # Agent's explanation
    status: str               # "pending" | "approved" | "rejected"
    created_at: str           # ISO-8601 UTC
    resolved_at: str | None   # ISO-8601 UTC or None
    agent_id: str             # Optional agent identifier, may be ""
```

### Storage

- Persists to `.cache/memory_proposals.json` (existing `.cache/` dir already gitignored).
- JSON envelope: `{"version": 1, "proposals": [...]}`.
- Thread-safe: read-modify-write with a file lock (match `inventory_store.py` approach).

### `ProposalStore` class

Methods: `load() → list[MemoryProposal]`, `save(proposals)`, `add(proposal) → MemoryProposal`, `list(status=None) → list`, `get(id) → MemoryProposal | None`, `update(id, **fields) → MemoryProposal`, `set_status(id, status, resolved_at) → MemoryProposal`.

### `AgentsRegistry` additions

Thin delegating methods: `add_proposal(...)`, `list_proposals(status=None)`, `approve_proposal(id)`, `reject_proposal(id)`, `edit_proposal(id, proposed_content, section_heading)`.

`approve_proposal` calls `update_managed_file_section(target_path, section_heading, proposed_content)` then immediately calls the existing inline-refresh for the affected file (single `_refresh_file()` path via the existing cache-invalidation logic), then marks the proposal `approved`.

---

## 2. Config — `config.py` / `AppConfig`

New field: `allow_direct_writes: bool = False`.

When `False`:
- `update_managed_file` and `update_managed_file_section` MCP tools are **not registered** by `create_server()`.
- Approval code in `AgentsRegistry.approve_proposal()` calls the underlying registry method directly (bypasses the tool-registration gate).

When `True`: existing behaviour is preserved for script/power-user use.

Config YAML key: `allow_direct_writes: false` (matches existing snake_case keys).

---

## 3. MCP Layer — `server.py`

### New tool: `propose_registry_update`

```
propose_registry_update(
    target_project: str,
    section_heading: str,
    proposed_content: str,
    rationale: str,
    agent_id: str = ""
) -> dict
```

Logic:
1. Look up the project by `target_project`; raise `ValueError` if not found.
2. Resolve the project's `AGENTS.md` path from `ProjectRecord.agent_file_path`.
3. Validate the path is within configured roots (reuse `_validate_managed_file_path`).
4. Call `registry.add_proposal(...)` → returns proposal.
5. Return `{"proposal_id": id, "status": "pending", "message": "Proposal {id} submitted. Awaiting human approval."}`.

### System directive — `prompts.py` (extend existing)

Add a new MCP prompt `memory_curation_directive` (alongside existing `build_project_prompt` / `build_resolve_context_prompt`). Content:

> When you resolve a complex bug or establish a new rule, DO NOT assume it should be saved. Ask the user: "Should I add this to the project's AGENTS.md?" If the user agrees, use `propose_registry_update`. Do not use direct file write tools.

Also expose as a resource at `agents://directives/memory-curation` for agents that prefer resource-based context loading.

### Conditional tool registration

```python
if not registry.config.allow_direct_writes:
    # do not register update_managed_file / update_managed_file_section
else:
    # register them as today
```

---

## 4. Web API — `web.py` (4 new routes)

| Method | Path | Action |
|--------|------|--------|
| `GET` | `/api/proposals` | List proposals. Optional `?status=pending\|approved\|rejected`. Returns `{proposals: [...]}`. |
| `POST` | `/api/proposals/{id}/approve` | Calls `registry.approve_proposal(id)`. Returns updated proposal. |
| `POST` | `/api/proposals/{id}/reject` | Calls `registry.reject_proposal(id)`. Returns updated proposal. |
| `PATCH` | `/api/proposals/{id}` | Body: `{proposed_content?, section_heading?}`. Calls `registry.edit_proposal(...)`. Returns updated proposal. Only allowed on `pending` proposals. |

All routes follow the existing error-handling convention in `web.py` (catch `ValueError`/`FileNotFoundError`, return `400`/`404` with `{"error": "..."}` JSON).

---

## 5. Frontend — `admin.html` + `app.js`

### Tab

Add a **"Review Queue"** tab to the existing tab bar. Shows a numeric badge when `pending` count > 0. Badge fetches from `GET /api/proposals?status=pending` on page load and after any approve/reject action.

### Proposal card

Each pending proposal renders as a card with:
- **Target badge**: project name + file path (truncated with tooltip).
- **Agent ID**: shown if non-empty.
- **Rationale**: read-only text block.
- **Section heading**: editable `<input>`.
- **Content editor**: `<textarea>` pre-populated with `proposed_content`. Changes auto-saved via `PATCH /api/proposals/{id}` on blur.
- **Action buttons**: "Approve" (`POST …/approve`) and "Reject" (`POST …/reject`). On success, card slides out; badge decrements.

Approved/rejected proposals are accessible via a toggle ("Show history") that switches `?status=` filter. Cards in history mode are read-only.

Styling follows existing admin panel conventions (`styles.css` variables, `.card`, `.badge` patterns already in place). Theme is inherited from the existing theme picker.

---

## 6. Testing

| Test | Location |
|------|----------|
| `ProposalStore` CRUD (add, list, get, update, set_status) | `tests/test_proposals.py` |
| `propose_registry_update` tool — success + unknown project error | `tests/test_proposals.py` |
| `approve_proposal` — write triggered + cache invalidated + status updated | `tests/test_proposals.py` |
| Config flag — direct-write tools absent when `allow_direct_writes=False` | `tests/test_proposals.py` |
| Web routes — all 4 endpoints (mock registry) | `tests/test_web_proposals.py` |

---

## Implementation Sequence

1. `proposals.py` — data model + `ProposalStore`.
2. `config.py` — `allow_direct_writes` field.
3. `registry.py` — `proposal_store` wiring + five delegating methods.
4. `server.py` — `propose_registry_update` tool + conditional registration of direct-write tools.
5. `prompts.py` / `resources.py` — `memory_curation_directive`.
6. `web.py` — four API routes.
7. `admin.html` + `app.js` — Review Queue tab + proposal cards.
8. Tests.
