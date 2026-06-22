# Help & Reference Panel — Design

**Date:** 2026-06-21
**Status:** Approved

## Goal

Add a "Documentation / Reference" section to the admin web UI so a user can
understand each component of the application without leaving the page.

## Decisions

- **Format:** A new numbered sidenav panel, `07 Help & Reference`, consistent
  with the existing six panels. (Not a modal, not per-panel tooltips.)
- **Scope:** Explain the UI panels *and* the underlying concepts.

## Implementation

Entirely client-side. No new FastAPI route, no JS logic, no dependencies — the
content is authored directly as static HTML in the existing admin template, and
the existing generic nav-active toggle already handles the new nav item.

### Files touched

- `mcp_agents_registry/web_assets/templates/admin.html`
  - Add a `<a href="#sec-help" class="nav-item">` entry (`07 Help & Reference`)
    to the `.sidenav`.
  - Add a `<section id="sec-help" class="panel">` after the Review Queue panel.
- `mcp_agents_registry/web_assets/static/styles.css`
  - Add a small `.doc-*` ruleset for readable documentation text (comfortable
    line length/spacing, a definition-list look, inline `code` styling). Reuse
    existing `panel`, `panel-head`, `panel-body`, `subcard`, `two-col`, `pill`.

### Panel content

1. **What this is** — one intro paragraph: the registry discovers/indexes
   hierarchical `AGENTS.md` / `agents.md` files and resolves inherited,
   context-aware instructions for any path; available both via this admin UI
   and as an MCP server.

2. **Core concepts** (subcards):
   - `AGENTS.md` / `CLAUDE.md` files — what they are and what they hold.
   - Hierarchy merge / nearest-wins resolution — nearest wins for
     purpose & overview; commands/constraints/etc. are combined & deduped.
   - MCP server surface — 5 tools, 5 resources, 2 prompts exposed to agents.

3. **The panels, explained** — one entry per existing panel (Registry,
   Inspector, Accounts & Devices, Installations, Editor, Review Queue):
   what it does, when to use it, and what the key buttons do.

## Out of scope (YAGNI)

- No in-doc search, no collapsible accordions.
- No per-panel `?` deep-links.
- No markdown rendering — content authored as HTML.
- No backend changes.

## Success criteria

- A `07 Help & Reference` item appears in the sidenav and scrolls to the panel.
- The panel reads correctly across the existing light/dark themes (uses theme
  CSS variables only).
- No regression to existing panels; no new server routes or JS errors.
