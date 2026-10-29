# Memory-MCP Prototype Design

**Date:** 2026-10-29  
**Status:** Draft for review  
**Scope:** Local, single-user, cross-session coding memory on one machine

## 1. Goal

Extend `mcp-agents-registry` with a durable memory subsystem that lets coding agents record useful findings and retrieve them in later sessions, including sessions run by a different agent client.

The prototype succeeds when a later session retrieves an evidenced, relevant finding and avoids repeating an investigation, without receiving unrelated project information or obsolete advice.

This is an extension, not a rewrite. The existing scan → parse → cache → resolve pipeline remains responsible for `AGENTS.md` instructions.

## 2. Design principles

1. **History is not knowledge.** An attempted fix is not a verified solution.
2. **Memory is not instruction.** Retrieved findings are historical evidence; only explicit human-approved promotion changes `AGENTS.md`.
3. **Capture is explicit.** MCP tool registration does not automatically capture conversations or load startup context.
4. **Scope before ranking.** Project isolation must not depend on search relevance.
5. **Durable by default.** Memories live in a database outside disposable cache directories.
6. **Local first.** The prototype makes no external summarization or embedding calls.
7. **Retry safely.** Repeated ingestion must not create duplicate records.
8. **Bound context.** Recall returns compact summaries, not entire session histories.

## 3. Prototype boundaries

### Included

- SQLite persistence, migrations, full-text search, and concurrent local processes.
- Explicit project registration independent of the presence of `AGENTS.md`.
- Agent-authored structured memories through MCP.
- A client-neutral JSON session import format and a command to import it.
- Sessions, minimal source evidence, memory lifecycle, and audit metadata.
- Project/path-scoped search and an optional combined session-context tool.
- Basic admin UI for inspecting, editing, activating, superseding, and deleting memories.
- Human-reviewed promotion through the existing proposal workflow, with conflict safeguards.
- One client-specific capture integration after verifying the selected client's supported hooks or exports.

### Not included

- Passive monitoring of every terminal, keystroke recording, or arbitrary shell history ingestion.
- Guaranteed capture from unsupported clients or forced process termination.
- Automatic LLM extraction from full transcripts.
- Vector databases, embeddings, knowledge graphs, or autonomous consolidation.
- Multi-user hosting, cloud synchronization, or a shared database on a network filesystem.
- Automatic changes to `AGENTS.md`.
- Migration of the existing inventory and proposal JSON stores into SQLite.

The generic import path and MCP tools form the usable baseline. A named client adapter is a follow-on prototype milestone, not an unverified dependency of that baseline.

## 4. Existing integration points

- `mcp_agents_registry/server.py`: register memory MCP tools using a new service.
- `mcp_agents_registry/web.py`: expose memory administration routes.
- `mcp_agents_registry/resolver.py`: keep existing instruction inheritance unchanged.
- `mcp_agents_registry/proposals.py`: reuse the human review concept for promotion.
- `mcp_agents_registry/registry.py`: retain instruction/project indexing responsibilities; do not turn it into the memory service.
- `mcp_agents_registry/prompts.py`: add optional capture/recall guidance, without assuming clients load it automatically.

Existing JSON stores use atomic file replacement. That is not a cross-process read-modify-write transaction and must not be copied as the new memory persistence pattern.

## 5. Architecture

```text
Coding agent -- MCP record/search tools --+
                                          |
Structured session export -- Import CLI --+--> MemoryService
                                                |
                             validation, scope, redaction,
                             lifecycle and idempotency
                                                |
                                           SQLite store
                                                |
                           scoped FTS retrieval + bounded results
                                                |
                                      MCP tools / Admin UI

Selected memory --> Human-reviewed proposal --> AGENTS.md
```

Proposed modules:

- `memory_models.py`: dataclasses and validated enums/value objects.
- `memory_store.py`: SQLite connections, migrations, transactional persistence, FTS synchronization.
- `memory_service.py`: project scope, validation, lifecycle, idempotency, redaction policy.
- `memory_retrieval.py`: candidate selection, ranking, excerpt construction, output limits.
- `session_ingestion.py`: versioned import schema and batch ingestion.
- `memory_cli.py`: project registration, import, backup, and purge commands.
- `capture_adapters/`: introduced only when the first client adapter is implemented.

MCP, CLI, and web interfaces call the same service. They must not implement independent mutation rules.

## 6. Storage and configuration

Use Python's `sqlite3` module. Check FTS5 availability at startup and return an actionable error if unavailable; do not silently disable search.

Proposed configuration, disabled by default for backward compatibility:

```yaml
memory:
  enabled: false
  database_path: "D:/AgentMemory/memory.sqlite3"
  allow_global_scope: false
  max_memory_chars: 12000
  max_evidence_chars: 4000
  max_import_bytes: 2097152
  max_import_events: 200
  default_search_limit: 5
  max_search_limit: 20
  max_recall_chars: 12000
  candidate_retention_days: 30
  evidence_retention_days: 30
```

The path above is illustrative, not a required installation location. When enabled, require an explicit database path in the prototype. Resolve relative paths against the configuration file's directory, not the process working directory.

Operational behavior:

- WAL mode on a local filesystem, foreign keys enabled on every connection.
- Short write transactions, a bounded busy timeout, and actionable lock errors.
- Separate connections per request/unit of work; no shared mutable connection across worker threads.
- Schema version recorded in the database. Serialize migrations and refuse unknown newer versions.
- Update memory rows and FTS entries in the same transaction.
- Back up with SQLite's backup API, not by copying only the live main database file.
- Do not log memory bodies, evidence text, or raw imports by default.

## 7. Data model

### Projects and roots

`memory_projects`:

- `id`: UUID, stable across local moves and worktrees.
- `display_name`.
- `created_at`, `updated_at`.

`memory_project_roots`:

- `project_id`.
- `canonical_root`: unique registered local directory.

A project may have multiple explicitly registered roots. Resolve paths using the longest matching registered root. Root registration is an administrative action constrained to configured allowed roots. Never merge projects automatically by basename or Git remote URL.

Store affected paths relative to the matched project root. Reject traversal, absolute affected paths, and paths that escape the root after normalization. Respect the application's symlink policy and Windows path semantics. Cross-project recall is not enabled implicitly.

### Sessions

`sessions`:

- `id`: internal UUID.
- `project_id`.
- `client_name` and `external_session_id`.
- `started_at`, optional `ended_at`.
- optional `branch`, `commit_sha`.
- `status`: `open`, `closed`, or `interrupted`.

Unique key: `(project_id, client_name, external_session_id)`.

Branch and commit are provenance, not proof of current applicability. A stale open session does not imply successful completion.

### Source events

`source_events`:

- `id`, `session_id`, `external_event_id`.
- `occurred_at`, `event_kind`.
- optional bounded `evidence_excerpt` after redaction.
- `content_hash` of the canonical sanitized payload.
- `ingested_at`, optional `expires_at`.

Unique key: `(session_id, external_event_id)`.

Only structured findings, outcomes, and minimal evidence are accepted initially. Full raw transcript retention is excluded. Evidence is optional: an agent-authored memory without an excerpt must be labelled accordingly.

### Memories

`memories`:

- `id`, `project_id`.
- `scope`: `project` or `path`; global scope is reserved and rejected in the first prototype.
- optional `scope_path`: relative directory or file to which the finding applies.
- `kind`: `bug_fix`, `decision`, `workflow`, `environment`, or `pitfall`.
- `summary`: short conclusion.
- `details`: bounded explanation and applicability conditions.
- `status`: `candidate`, `active`, `superseded`, `rejected`, or `archived`.
- `evidence_level`: `agent_reported`, `tool_output_attached`, or `human_verified`.
- `created_at`, `updated_at`, optional `last_verified_at`, `expires_at`.
- optional `superseded_by`.
- `content_hash`: normalized summary/details plus scope and kind.
- `revision`: integer for optimistic concurrency.

Related tables:

- `memory_sources`: links memories to source events; more than one source may support a finding.
- `memory_paths`: affected relative paths used for relevance boosts, distinct from applicability scope.
- `memory_tags`: normalized tags.
- `memory_promotions`: memory ID, proposal ID, target file, target base hash, and promotion state.
- `memory_audit`: action, entity ID, actor channel, timestamp, and non-sensitive metadata.
- `ingestion_requests`: project, client, request key, sanitized payload hash, and result IDs.

A tool-output attachment is evidence to inspect, not automatic proof that a claim is true. Agents cannot assign `human_verified` or activate their own candidates in the prototype.

## 8. Capture and ingestion

### Agent-authored recording

An agent submits a concise finding during or after a meaningful task. The service creates or reuses the session, stores optional minimal evidence, and creates a `candidate` memory in one transaction.

Recommended content:

- What was learned.
- Where and under what conditions it applies.
- What was attempted versus what actually worked.
- What validation was run, if any.

Do not record routine narration, unsupported guesses stated as facts, or complete command logs.

### Structured session import

Add a proposed command:

```text
mcp-agents-memory import-session --file session-export.json
```

Version 1 imports contain:

- Schema version and stable import/request ID.
- Registered project ID and client name.
- External session ID and timestamps.
- A bounded list of events with stable external IDs.
- Explicit candidate memories referencing those event IDs.

The importer does not infer conclusions from arbitrary text. Validate and redact the full bounded batch before opening the write transaction. Commit the batch atomically; failed validation writes nothing.

For repeated keys:

- Same key and same sanitized payload hash: return the original result.
- Same key and different payload: return a conflict, not a silent overwrite.
- Identical memory content in the same project/scope: reuse the existing memory and attach additional provenance where appropriate; never automatically reactivate a superseded or rejected memory.

### First client adapter — Codex CLI

**Confirmed decision:** Codex CLI is the first terminal client to support.

Start with explicit memory recording and recall through the configured MCP server. For automated capture, verify the installed Codex CLI version's supported session/event exports and lifecycle integration points against current documentation before selecting a mechanism. Do not assume a particular hook, transcript location, or private log format is a stable interface.

Use `codex-cli` as the provenance label. Preserve supported native session/event IDs when available; otherwise use adapter-generated identifiers persisted across retries. Document how resumed sessions map to the same internal session and how separate concurrent sessions remain distinct.

The adapter must emit the client-neutral import format. Raw transcripts alone do not become memories: candidates must be explicit structured findings, consistent with the prototype's exclusion of automatic LLM extraction. If supported automated capture is unavailable, retain explicit MCP recording and structured import as the documented fallback.

The adapter must provide stable session/event identifiers and resumable checkpoints. Prefer task-boundary or incremental capture; session-end capture is an additional opportunity, not the only one. Persist checkpoints only after successful ingestion. A shell wrapper without a transcript or structured export is insufficient.

## 9. Memory lifecycle

Default flow:

```text
candidate --> active --> superseded
     |           |
     v           v
 rejected     archived
```

- MCP recording and imports create candidates.
- Human activation makes a candidate eligible for normal recall.
- Human edits require the expected revision and preserve an audit action.
- Superseding a memory and linking its replacement happen in one transaction.
- Conflicting candidates remain separate and visible; the prototype does not choose which is true.
- Expired memories are excluded from normal recall even before cleanup runs.
- Promotion is a separate relationship, not a replacement for lifecycle status.

This review-first policy is intentionally conservative. Automatic activation of selected categories can be evaluated later using real usage data.

## 10. MCP interface

Proposed tools:

### `record_memory`

Inputs: project ID, client/session identifiers, idempotency key, kind, summary, details, scope, optional affected paths/tags/evidence.

Returns: memory ID, candidate status, evidence level, and whether the request reused an existing record.

### `search_memories`

Inputs: project ID, query, optional target path, kind, and bounded result limit.

Returns: active, unexpired memories within permitted scope, compact excerpts, evidence labels, timestamps, source IDs, and match reasons.

### `get_memory`

Inputs: project ID and memory ID.

Returns: bounded full details and available evidence, or a not-found response. Project checks also apply to direct ID lookups.

### `get_session_context`

Inputs: project ID, target path, optional task query, and output budget.

Returns separately labelled fields:

- `instructions`: existing instruction resolution result, if present.
- `instruction_status`: available or absent.
- `memories`: bounded recall results.
- `warnings`: missing evidence or other actionable issues.

Only the expected absence of an instruction file is converted to `instruction_status: absent`. Path validation and other errors must not be swallowed. Existing `resolve_context()` behavior stays unchanged.

### `propose_memory_promotion`

Inputs: project ID, memory ID, explicit target registry project, section heading, and proposed section content.

Creates a pending proposal only. It does not write a file or activate a memory.

Human lifecycle changes and destructive deletion remain in the local admin UI/CLI for the prototype. Tool prompts are optional guidance, not an enforcement mechanism or guaranteed startup integration.

## 11. Retrieval behavior

Apply filters before ranking:

1. Requested registered project.
2. Active status and non-expired lifecycle.
3. Applicability scope: project-wide or matching target path. If no target path is provided, include only project-wide memories.
4. Optional kind.

Then rank deterministically using:

1. FTS5/BM25 match across summary, details, and tags.
2. Exact/nearby affected-path relevance.
3. Evidence level and recent verification.
4. Recency as a tie-breaker, not a replacement for topical relevance.

Treat user search input as text, not arbitrary FTS query syntax. Parameterize SQL and safely construct FTS expressions. Define a limited empty-query mode for recent project-wide context; do not fill a failed nonempty search with unrelated recent entries.

Return at most the configured result count and character budget. Truncate at safe text boundaries and mark truncated results. Character limits are the prototype's deterministic approximation to a token budget, not an exact token count.

Every response labels memories as historical observations that may be stale and must not override current instructions. Retrieved text is never executed or interpreted as configuration.

## 12. Privacy and local security

- Capture is opt-in per registered project.
- Reject likely credential-bearing payloads with a safe error; redact common sensitive patterns in permitted evidence before persistence.
- Do not echo detected secrets in errors, audit logs, or conflict messages.
- Explain that automated detection is incomplete and users must avoid submitting sensitive data.
- No external model calls, embeddings, analytics, or telemetry in the prototype.
- Bind the admin service to loopback by default. Mutation routes require an appropriate local authorization token and browser-origin/CSRF protection; loopback binding alone is not sufficient.
- Treat client-provided names as provenance labels, not authenticated user identities. This prototype trusts the locally configured MCP clients and is not a multi-tenant security boundary.

Retention cleanup is an explicit CLI/admin action initially, not a required background daemon. It removes expired evidence and old unreviewed candidates according to configuration, without silently deleting active knowledge. If supporting evidence expires, retain provenance metadata and clearly report that the excerpt is no longer available.

Deletion removes memory content, FTS entries, and unshared linked evidence transactionally. Shared evidence remains only while referenced by retained memories and under its retention policy. Audit records must not retain deleted content. Physical erasure from WAL pages, filesystem snapshots, and backups is not guaranteed; document backup retention and maintenance separately.

## 13. Admin UI

Add a Memories view using the existing frontend assets and styling.

Minimum capabilities:

- Filter by project, status, kind, and query.
- Inspect summary, applicability, evidence, source client/session, and timestamps.
- Edit a candidate with revision conflict detection.
- Activate, reject, archive, or supersede.
- Delete with explicit confirmation and clear evidence-retention behavior.
- Propose promotion and show a preview of the resulting instruction change.

Do not display raw HTML from imported markdown. Render as text or use an explicitly safe rendering path.

## 14. Safe instruction promotion

Reuse the existing proposal review workflow, but do not assume it is already sufficient for concurrent memory-driven promotion.

Required safeguards:

- Link the proposal to its originating memory.
- Record the target file's base hash when the proposal is created.
- Preview the complete section change: the existing section update operation is not equivalent to appending a memory.
- At approval, detect changes since proposal creation and require re-review rather than overwrite newer instructions.
- Serialize cooperating approval writers across processes around validation and replacement.
- Mark completion only after a successful write; persist recoverable promotion state so an interrupted operation can be reconciled.

A SQLite transaction cannot atomically commit both a filesystem change and the existing JSON proposal status. Use an explicit operation state and retry/reconciliation protocol rather than claiming atomicity. External editors do not participate in application locks, so residual filesystem race limitations must be documented.

Until these safeguards are implemented, promotion remains disabled for new memory tools; ordinary capture and recall can ship independently.

## 15. Implementation milestones

### Milestone 1 — Durable memory core

Implement configuration, project/root registration, migrations, models, lifecycle operations, idempotency, and redaction. Test multi-process writes before exposing capture tools.

### Milestone 2 — MCP capture and recall

Add recording, search, detail retrieval, and session-context composition. Keep the original instruction API unchanged. Enable a complete manual cross-agent demonstration.

### Milestone 3 — Review UI and structured imports

Add human activation, editing, supersession, deletion, versioned import, retention cleanup, and backup commands. Exported structured findings can now be imported without client-specific hooks.

### Milestone 4 — Codex CLI integration

Verify and document the supported Codex CLI version and integration points, implement incremental capture/checkpoints where supported, and test interruptions, retries, resumed sessions, and concurrent sessions. Demonstrate that a finding recorded in one Codex session can be activated and recalled in a fresh session. Retain explicit MCP capture as the fallback if automated integration is unavailable.

### Milestone 5 — Safe promotion

Add linked proposal previews, base-hash checks, cross-process serialization, and interrupted-operation reconciliation. Enable promotion only after the safety tests pass.

Do not add semantic search until a fixed set of recall examples demonstrates meaningful misses that keyword/path retrieval cannot address.

## 16. Validation and acceptance criteria

### Persistence and concurrency

- Concurrent processes can record distinct memories without lost updates.
- Repeating an identical request returns the same IDs.
- Reusing a key with changed content returns a conflict.
- Failed imports leave no partial sessions/events/memories.
- Interrupted migrations recover safely or fail with actionable instructions.
- Backup restoration reproduces memories, lifecycle state, and search results.

### Scope and compatibility

- Memories work in a registered project with no `AGENTS.md`.
- Existing resolver tests pass unchanged.
- Project A never receives Project B memories, including direct ID lookups.
- Path traversal, symlink escapes, and Windows path edge cases are covered.
- Registered worktrees share a project identity without accidental project merging.

### Memory quality

- Candidates, rejected, archived, superseded, and expired memories are excluded from normal recall.
- Agent-submitted evidence cannot self-assign human verification.
- Contradictory findings remain separately inspectable.
- A superseded solution does not outrank or appear alongside its active replacement in default recall.
- Empty/no-match searches behave as specified.

### Privacy and promotion

- Secret fixtures do not appear in persistent content, logs, errors, or FTS indexes.
- Deletion removes searchable content and unshared evidence.
- Unsafe imported markup is not executed in the UI.
- Stale promotion proposals cannot overwrite a changed target without re-review.
- Repeated or interrupted approvals do not duplicate instruction content.

### End-to-end demonstration

1. Agent A records a bounded finding with a stable session/request ID and supporting evidence.
2. The user reviews and activates it.
3. Agent B, in a fresh session, recalls it for the same project and relevant task/path.
4. The response includes source and evidence labels within the recall budget.
5. An unrelated project receives no result.
6. A corrected finding supersedes the original, and only the replacement is recalled.

Maintain a small labelled recall fixture set containing relevant queries, paraphrases, exact errors, path-specific questions, and deliberate no-match cases. Record top-five hit rate and irrelevant-result counts before changing ranking or introducing embeddings. Do not claim improved coding outcomes from retrieval metrics alone.

## 17. Decisions

### Confirmed

- **First terminal client:** Codex CLI, selected by the user.

### To confirm

1. Where should the durable database and backups live?
2. Is manual activation acceptable for the prototype? This design assumes yes.
3. Are the proposed evidence/candidate retention defaults suitable?

These do not block reviewing the design. Codex CLI integration mechanisms and version compatibility must be verified before implementing the client-specific milestone.
