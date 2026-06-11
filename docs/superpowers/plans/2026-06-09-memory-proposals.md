# Memory Proposals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a human-in-the-loop staging layer so agents submit proposals for `AGENTS.md` updates instead of writing files directly, with approval/rejection handled in the admin web UI.

**Architecture:** A new `proposals.py` module provides a JSON-backed `ProposalStore` (mirroring `inventory_store.py`). The MCP server exposes a `propose_registry_update` tool; direct-write tools are gated behind `allow_direct_writes: false` in config. The FastAPI admin UI gains a Review Queue panel with four backing API routes.

**Tech Stack:** Python 3.11+, dataclasses, FastAPI, FastMCP, vanilla JS (existing `app.js` + `admin.html`), pytest/unittest.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `mcp_agents_registry/proposals.py` | `MemoryProposal` dataclass + `ProposalStore` CRUD |
| Modify | `mcp_agents_registry/config.py` | Add `allow_direct_writes` + `proposals_path` fields |
| Modify | `mcp_agents_registry/registry.py` | Wire `ProposalStore`; add 5 delegating methods |
| Modify | `mcp_agents_registry/server.py` | Add `propose_registry_update` tool; gate direct-write tools |
| Modify | `mcp_agents_registry/prompts.py` | Add `memory_curation_directive()` |
| Modify | `mcp_agents_registry/resources.py` | Add `proposals_resource_payload()` |
| Modify | `mcp_agents_registry/web.py` | Add 4 `/api/proposals` routes |
| Modify | `mcp_agents_registry/web_assets/templates/admin.html` | Review Queue nav item + panel |
| Modify | `mcp_agents_registry/web_assets/static/app.js` | Proposal fetch/render/approve/reject/edit |
| Create | `tests/test_proposals.py` | Unit tests for `ProposalStore` + tool + approve flow + config flag |
| Create | `tests/test_web_proposals.py` | Integration tests for the 4 API routes |

---

## Task 1: `ProposalStore` — data model + CRUD

**Files:**
- Create: `mcp_agents_registry/proposals.py`
- Create: `tests/test_proposals.py`

- [ ] **Step 1: Write the failing tests for `MemoryProposal` and `ProposalStore`**

```python
# tests/test_proposals.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mcp_agents_registry.proposals import MemoryProposal, ProposalStore


class MemoryProposalTests(unittest.TestCase):
    def _make(self, **overrides) -> MemoryProposal:
        defaults = dict(
            id="abc-123",
            target_project="frontend",
            target_path="/workspace/frontend/AGENTS.md",
            section_heading="Coding Rules",
            proposed_content="- use black\n",
            rationale="Established in PR #42.",
            status="pending",
            created_at="2026-06-09T00:00:00+00:00",
            resolved_at=None,
            agent_id="",
        )
        defaults.update(overrides)
        return MemoryProposal(**defaults)

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        proposal = self._make(agent_id="agent-1", resolved_at="2026-06-09T01:00:00+00:00")
        restored = MemoryProposal.from_dict(proposal.to_dict())
        self.assertEqual(restored.id, "abc-123")
        self.assertEqual(restored.agent_id, "agent-1")
        self.assertEqual(restored.resolved_at, "2026-06-09T01:00:00+00:00")

    def test_from_dict_defaults(self) -> None:
        minimal = {
            "id": "x", "target_project": "p", "target_path": "/p/AGENTS.md",
            "section_heading": "Notes", "proposed_content": "hi", "rationale": "r",
            "created_at": "2026-06-09T00:00:00+00:00",
        }
        proposal = MemoryProposal.from_dict(minimal)
        self.assertEqual(proposal.status, "pending")
        self.assertIsNone(proposal.resolved_at)
        self.assertEqual(proposal.agent_id, "")


class ProposalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / ".cache" / "memory_proposals.json"
        self.store = ProposalStore(self.path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_returns_empty_list_when_file_absent(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_add_persists_proposal_and_returns_it(self) -> None:
        proposal = self.store.add(
            target_project="frontend",
            target_path="/ws/AGENTS.md",
            section_heading="Notes",
            proposed_content="- note\n",
            rationale="good idea",
        )
        self.assertEqual(proposal.status, "pending")
        self.assertIsNotNone(proposal.id)
        reloaded = self.store.load()
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0].id, proposal.id)

    def test_list_filters_by_status(self) -> None:
        p1 = self.store.add(target_project="a", target_path="/a/AGENTS.md",
                            section_heading="S", proposed_content="c", rationale="r")
        p2 = self.store.add(target_project="b", target_path="/b/AGENTS.md",
                            section_heading="S", proposed_content="c", rationale="r")
        self.store.set_status(p2.id, "approved")
        self.assertEqual(len(self.store.list(status="pending")), 1)
        self.assertEqual(self.store.list(status="pending")[0].id, p1.id)
        self.assertEqual(len(self.store.list(status="approved")), 1)

    def test_get_returns_none_for_missing_id(self) -> None:
        self.assertIsNone(self.store.get("nonexistent"))

    def test_get_returns_proposal_by_id(self) -> None:
        p = self.store.add(target_project="a", target_path="/a/AGENTS.md",
                           section_heading="S", proposed_content="c", rationale="r")
        self.assertEqual(self.store.get(p.id).id, p.id)

    def test_set_status_approved_sets_resolved_at(self) -> None:
        p = self.store.add(target_project="a", target_path="/a/AGENTS.md",
                           section_heading="S", proposed_content="c", rationale="r")
        updated = self.store.set_status(p.id, "approved")
        self.assertEqual(updated.status, "approved")
        self.assertIsNotNone(updated.resolved_at)

    def test_set_status_raises_for_unknown_id(self) -> None:
        with self.assertRaises(LookupError):
            self.store.set_status("no-such-id", "approved")

    def test_update_edits_fields(self) -> None:
        p = self.store.add(target_project="a", target_path="/a/AGENTS.md",
                           section_heading="Old", proposed_content="old\n", rationale="r")
        updated = self.store.update(p.id, section_heading="New", proposed_content="new\n")
        self.assertEqual(updated.section_heading, "New")
        self.assertEqual(updated.proposed_content, "new\n")
        self.assertEqual(self.store.get(p.id).section_heading, "New")

    def test_update_raises_for_unknown_id(self) -> None:
        with self.assertRaises(LookupError):
            self.store.update("no-such-id", section_heading="x")

    def test_none_path_store_is_a_noop(self) -> None:
        store = ProposalStore(None)
        store.add(target_project="a", target_path="/a/AGENTS.md",
                  section_heading="S", proposed_content="c", rationale="r")
        self.assertEqual(store.load(), [])
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_proposals.py -v
```
Expected: `ModuleNotFoundError: No module named 'mcp_agents_registry.proposals'`

- [ ] **Step 3: Create `mcp_agents_registry/proposals.py`**

```python
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROPOSALS_VERSION = 1


@dataclass(slots=True)
class MemoryProposal:
    id: str
    target_project: str
    target_path: str
    section_heading: str
    proposed_content: str
    rationale: str
    status: str
    created_at: str
    resolved_at: str | None = None
    agent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_project": self.target_project,
            "target_path": self.target_path,
            "section_heading": self.section_heading,
            "proposed_content": self.proposed_content,
            "rationale": self.rationale,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryProposal":
        return cls(
            id=str(payload["id"]),
            target_project=str(payload["target_project"]),
            target_path=str(payload["target_path"]),
            section_heading=str(payload["section_heading"]),
            proposed_content=str(payload["proposed_content"]),
            rationale=str(payload["rationale"]),
            status=str(payload.get("status", "pending")),
            created_at=str(payload["created_at"]),
            resolved_at=payload.get("resolved_at"),
            agent_id=str(payload.get("agent_id", "")),
        )


class ProposalStore:
    def __init__(self, proposals_path: Path | None) -> None:
        self.proposals_path = proposals_path

    def load(self) -> list[MemoryProposal]:
        if self.proposals_path is None or not self.proposals_path.exists():
            return []
        payload = json.loads(self.proposals_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Proposals file must contain a top-level mapping.")
        version = int(payload.get("version", 0))
        if version != PROPOSALS_VERSION:
            raise ValueError(f"Unsupported proposals version: {version}")
        return [MemoryProposal.from_dict(item) for item in payload.get("proposals", [])]

    def save(self, proposals: list[MemoryProposal]) -> None:
        if self.proposals_path is None:
            return
        self.proposals_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PROPOSALS_VERSION,
            "proposals": [p.to_dict() for p in proposals],
        }
        _atomic_write_json(self.proposals_path, payload)

    def add(
        self,
        *,
        target_project: str,
        target_path: str,
        section_heading: str,
        proposed_content: str,
        rationale: str,
        agent_id: str = "",
    ) -> MemoryProposal:
        proposals = self.load()
        proposal = MemoryProposal(
            id=str(uuid.uuid4()),
            target_project=target_project,
            target_path=target_path,
            section_heading=section_heading,
            proposed_content=proposed_content,
            rationale=rationale,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            resolved_at=None,
            agent_id=agent_id,
        )
        proposals.append(proposal)
        self.save(proposals)
        return proposal

    def list(self, *, status: str | None = None) -> list[MemoryProposal]:
        proposals = self.load()
        if status is not None:
            proposals = [p for p in proposals if p.status == status]
        return proposals

    def get(self, proposal_id: str) -> MemoryProposal | None:
        for proposal in self.load():
            if proposal.id == proposal_id:
                return proposal
        return None

    def update(self, proposal_id: str, **fields: Any) -> MemoryProposal:
        proposals = self.load()
        for proposal in proposals:
            if proposal.id == proposal_id:
                for key, value in fields.items():
                    setattr(proposal, key, value)
                self.save(proposals)
                return proposal
        raise LookupError(f"Proposal not found: {proposal_id}")

    def set_status(self, proposal_id: str, status: str) -> MemoryProposal:
        resolved_at = (
            datetime.now(timezone.utc).isoformat()
            if status in ("approved", "rejected")
            else None
        )
        return self.update(proposal_id, status=status, resolved_at=resolved_at)


def _atomic_write_json(path: Path, payload: object) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(path)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_proposals.py -v
```
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_agents_registry/proposals.py tests/test_proposals.py
git commit -m "feat: add MemoryProposal dataclass and ProposalStore"
```

---

## Task 2: Config — `allow_direct_writes` + `proposals_path`

**Files:**
- Modify: `mcp_agents_registry/config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_proposals.py` inside a new `ConfigProposalsTests` class:

```python
class ConfigProposalsTests(unittest.TestCase):
    def test_allow_direct_writes_defaults_to_false(self) -> None:
        import tempfile as tmp_mod
        from mcp_agents_registry.config import AppConfig

        with tmp_mod.TemporaryDirectory() as temp_dir:
            config = AppConfig(roots=(Path(temp_dir),))
            self.assertFalse(config.allow_direct_writes)

    def test_proposals_path_defaults_inside_cache_dir(self) -> None:
        import tempfile as tmp_mod
        from mcp_agents_registry.config import AppConfig

        with tmp_mod.TemporaryDirectory() as temp_dir:
            config = AppConfig.from_mapping(
                {"roots": [temp_dir], "cache_enabled": False},
                config_path=Path(temp_dir) / "config.yaml",
            )
            self.assertIn("memory_proposals.json", str(config.proposals_path))

    def test_allow_direct_writes_from_mapping_reads_yaml_value(self) -> None:
        import tempfile as tmp_mod
        from mcp_agents_registry.config import AppConfig

        with tmp_mod.TemporaryDirectory() as temp_dir:
            config = AppConfig.from_mapping(
                {"roots": [temp_dir], "allow_direct_writes": True, "cache_enabled": False},
                config_path=Path(temp_dir) / "config.yaml",
            )
            self.assertTrue(config.allow_direct_writes)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_proposals.py::ConfigProposalsTests -v
```
Expected: `AttributeError: 'AppConfig' object has no attribute 'allow_direct_writes'`

- [ ] **Step 3: Edit `mcp_agents_registry/config.py`**

Add two fields to `AppConfig` after `inventory_path`:

```python
    allow_direct_writes: bool = False
    proposals_path: Path | None = None
```

Add normalization in `__post_init__` after the `inventory_path` normalization block:

```python
        if self.proposals_path is not None:
            self.proposals_path = normalize_path(self.proposals_path, follow_symlinks=self.follow_symlinks)
```

In `from_mapping`, add after the `inventory_path` block and before `return cls(`:

```python
        proposals_path_value = payload.get("proposals_path")
        proposals_path = (
            _resolve_declared_path(base_dir, proposals_path_value)
            if proposals_path_value
            else base_dir / ".cache" / "memory_proposals.json"
        )
```

Add the two new kwargs to the `return cls(...)` call:

```python
            allow_direct_writes=bool(payload.get("allow_direct_writes", False)),
            proposals_path=proposals_path,
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/test_proposals.py::ConfigProposalsTests -v
```
Expected: 3 tests PASS.

- [ ] **Step 5: Run the full suite to check nothing is broken**

```bash
uv run pytest tests/ -v
```
Expected: all existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_agents_registry/config.py tests/test_proposals.py
git commit -m "feat: add allow_direct_writes and proposals_path to AppConfig"
```

---

## Task 3: Registry — wire `ProposalStore` + delegating methods

**Files:**
- Modify: `mcp_agents_registry/registry.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_proposals.py`:

```python
class RegistryProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "AGENTS.md").write_text("# Purpose\nTest workspace\n", encoding="utf-8")
        config_path = root / "config.yaml"
        config_path.write_text(
            f"roots:\n  - {root}\ncache_enabled: false\nparse_sections: true\n",
            encoding="utf-8",
        )
        from mcp_agents_registry.registry import AgentsRegistry
        self.registry = AgentsRegistry.from_config_path(str(config_path))
        self.registry.refresh_index()
        self.project_name = self.registry.list_projects()[0]["project_name"]
        self.target_path = self.registry.projects_by_name[self.project_name].agent_file_path

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_add_proposal_returns_pending_proposal(self) -> None:
        p = self.registry.add_proposal(
            target_project=self.project_name,
            target_path=self.target_path,
            section_heading="Notes",
            proposed_content="- new note\n",
            rationale="useful",
        )
        self.assertEqual(p.status, "pending")
        self.assertEqual(p.target_project, self.project_name)

    def test_list_proposals_returns_all_by_default(self) -> None:
        self.registry.add_proposal(
            target_project=self.project_name, target_path=self.target_path,
            section_heading="S", proposed_content="c", rationale="r",
        )
        self.assertEqual(len(self.registry.list_proposals()), 1)

    def test_list_proposals_filters_by_status(self) -> None:
        p = self.registry.add_proposal(
            target_project=self.project_name, target_path=self.target_path,
            section_heading="S", proposed_content="c", rationale="r",
        )
        self.registry.reject_proposal(p.id)
        self.assertEqual(len(self.registry.list_proposals(status="pending")), 0)
        self.assertEqual(len(self.registry.list_proposals(status="rejected")), 1)

    def test_approve_proposal_writes_file_and_marks_approved(self) -> None:
        p = self.registry.add_proposal(
            target_project=self.project_name, target_path=self.target_path,
            section_heading="Test Notes",
            proposed_content="- approved content\n",
            rationale="needed",
        )
        approved = self.registry.approve_proposal(p.id)
        self.assertEqual(approved.status, "approved")
        content = Path(self.target_path).read_text(encoding="utf-8")
        self.assertIn("approved content", content)

    def test_edit_proposal_updates_content(self) -> None:
        p = self.registry.add_proposal(
            target_project=self.project_name, target_path=self.target_path,
            section_heading="Notes", proposed_content="old\n", rationale="r",
        )
        updated = self.registry.edit_proposal(p.id, proposed_content="new\n", section_heading="Notes")
        self.assertEqual(updated.proposed_content, "new\n")

    def test_approve_proposal_raises_for_unknown_id(self) -> None:
        with self.assertRaises(LookupError):
            self.registry.approve_proposal("no-such-id")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_proposals.py::RegistryProposalTests -v
```
Expected: `AttributeError: 'AgentsRegistry' object has no attribute 'add_proposal'`

- [ ] **Step 3: Edit `mcp_agents_registry/registry.py`**

At the top of the file, add the import alongside the other local imports:

```python
from .proposals import MemoryProposal, ProposalStore
```

In `AgentsRegistry.__init__`, after `self._load_inventory()`, add:

```python
        self.proposal_store = ProposalStore(config.proposals_path)
```

Add these five methods anywhere after `update_managed_file_section` (before `_validate_managed_file_path`):

```python
    def add_proposal(
        self,
        *,
        target_project: str,
        target_path: str,
        section_heading: str,
        proposed_content: str,
        rationale: str,
        agent_id: str = "",
    ) -> MemoryProposal:
        return self.proposal_store.add(
            target_project=target_project,
            target_path=target_path,
            section_heading=section_heading,
            proposed_content=proposed_content,
            rationale=rationale,
            agent_id=agent_id,
        )

    def list_proposals(self, *, status: str | None = None) -> list[MemoryProposal]:
        return self.proposal_store.list(status=status)

    def approve_proposal(self, proposal_id: str) -> MemoryProposal:
        proposal = self.proposal_store.get(proposal_id)
        if proposal is None:
            raise LookupError(f"Proposal not found: {proposal_id}")
        self.update_managed_file_section(
            path=proposal.target_path,
            section_heading=proposal.section_heading,
            section_content=proposal.proposed_content,
        )
        return self.proposal_store.set_status(proposal_id, "approved")

    def reject_proposal(self, proposal_id: str) -> MemoryProposal:
        proposal = self.proposal_store.get(proposal_id)
        if proposal is None:
            raise LookupError(f"Proposal not found: {proposal_id}")
        return self.proposal_store.set_status(proposal_id, "rejected")

    def edit_proposal(
        self,
        proposal_id: str,
        *,
        proposed_content: str | None = None,
        section_heading: str | None = None,
    ) -> MemoryProposal:
        proposal = self.proposal_store.get(proposal_id)
        if proposal is None:
            raise LookupError(f"Proposal not found: {proposal_id}")
        fields: dict[str, str] = {}
        if proposed_content is not None:
            fields["proposed_content"] = proposed_content
        if section_heading is not None:
            fields["section_heading"] = section_heading
        return self.proposal_store.update(proposal_id, **fields)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/test_proposals.py::RegistryProposalTests -v
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_agents_registry/registry.py tests/test_proposals.py
git commit -m "feat: wire ProposalStore into AgentsRegistry with delegating methods"
```

---

## Task 4: MCP Server — `propose_registry_update` tool + gate direct-write tools

**Files:**
- Modify: `mcp_agents_registry/server.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_proposals.py`:

```python
class ProposeToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "AGENTS.md").write_text("# Purpose\nTest workspace\n", encoding="utf-8")
        config_path = root / "config.yaml"
        config_path.write_text(
            f"roots:\n  - {root}\ncache_enabled: false\nparse_sections: true\n",
            encoding="utf-8",
        )
        from mcp_agents_registry.registry import AgentsRegistry
        self.registry = AgentsRegistry.from_config_path(str(config_path))
        self.registry.refresh_index()
        self.project_name = self.registry.list_projects()[0]["project_name"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_propose_registry_update_returns_proposal_id(self) -> None:
        from mcp_agents_registry.server import _propose_registry_update
        result = _propose_registry_update(
            registry=self.registry,
            target_project=self.project_name,
            section_heading="Notes",
            proposed_content="- new note\n",
            rationale="good reason",
        )
        self.assertIn("proposal_id", result)
        self.assertEqual(result["status"], "pending")

    def test_propose_registry_update_raises_for_unknown_project(self) -> None:
        from mcp_agents_registry.server import _propose_registry_update
        with self.assertRaises(ValueError):
            _propose_registry_update(
                registry=self.registry,
                target_project="nonexistent-project",
                section_heading="Notes",
                proposed_content="- x\n",
                rationale="nope",
            )

    def test_direct_write_tools_absent_when_flag_is_false(self) -> None:
        from mcp_agents_registry.config import AppConfig
        from mcp_agents_registry.server import create_server

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("# Purpose\nTest\n", encoding="utf-8")
            config_path = root / "config.yaml"
            config_path.write_text(
                f"roots:\n  - {root}\ncache_enabled: false\nallow_direct_writes: false\n",
                encoding="utf-8",
            )
            app = create_server(str(config_path))
            tool_names = {t.name if hasattr(t, "name") else str(t) for t in app._tool_manager.list_tools()}
            self.assertNotIn("update_managed_file", tool_names)
            self.assertNotIn("update_managed_file_section", tool_names)

    def test_direct_write_tools_present_when_flag_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("# Purpose\nTest\n", encoding="utf-8")
            config_path = root / "config.yaml"
            config_path.write_text(
                f"roots:\n  - {root}\ncache_enabled: false\nallow_direct_writes: true\n",
                encoding="utf-8",
            )
            from mcp_agents_registry.server import create_server
            app = create_server(str(config_path))
            tool_names = {t.name if hasattr(t, "name") else str(t) for t in app._tool_manager.list_tools()}
            self.assertIn("update_managed_file", tool_names)
            self.assertIn("update_managed_file_section", tool_names)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_proposals.py::ProposeToolTests -v
```
Expected: `ImportError: cannot import name '_propose_registry_update' from 'mcp_agents_registry.server'`

- [ ] **Step 3: Edit `mcp_agents_registry/server.py`**

Add this module-level helper function before `create_server` (so it can be imported by tests):

```python
def _propose_registry_update(
    registry: Any,
    target_project: str,
    section_heading: str,
    proposed_content: str,
    rationale: str,
    agent_id: str = "",
) -> dict[str, object]:
    try:
        record = registry.get_project_record(target_project)
    except LookupError:
        raise ValueError(f"Unknown project: {target_project}")
    proposal = registry.add_proposal(
        target_project=target_project,
        target_path=record.agent_file_path,
        section_heading=section_heading,
        proposed_content=proposed_content,
        rationale=rationale,
        agent_id=agent_id,
    )
    return {
        "proposal_id": proposal.id,
        "status": proposal.status,
        "message": f"Proposal {proposal.id} submitted. Awaiting human approval.",
    }
```

Inside `create_server`, add the new tool after `refresh_index`:

```python
    @app.tool()
    def propose_registry_update(
        target_project: str,
        section_heading: str,
        proposed_content: str,
        rationale: str,
        agent_id: str = "",
    ) -> dict[str, object]:
        return _propose_registry_update(
            registry=registry,
            target_project=target_project,
            section_heading=section_heading,
            proposed_content=proposed_content,
            rationale=rationale,
            agent_id=agent_id,
        )
```

Wrap the direct-write tool registrations in a conditional. Find the block that registers `update_managed_file` and `update_managed_file_section` (currently lines ~205-225) and wrap it:

```python
    if registry.config.allow_direct_writes:
        @app.tool()
        def update_managed_file(path: str, content: str, expected_sha256: str = "") -> dict[str, object]:
            return registry.update_managed_file(
                path=path,
                content=content,
                expected_sha256=expected_sha256 or None,
            )

        @app.tool()
        def update_managed_file_section(
            path: str,
            section_heading: str,
            section_content: str,
            expected_sha256: str = "",
        ) -> dict[str, object]:
            return registry.update_managed_file_section(
                path=path,
                section_heading=section_heading,
                section_content=section_content,
                expected_sha256=expected_sha256 or None,
            )
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/test_proposals.py::ProposeToolTests -v
```
Expected: all 4 tests PASS. (Note: the `_tool_manager` tests may vary by FastMCP version; if `_tool_manager` is not the correct attribute, inspect `app.__dict__` to find the tools list attribute and adjust the test assertion accordingly.)

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_agents_registry/server.py tests/test_proposals.py
git commit -m "feat: add propose_registry_update tool and gate direct-write tools behind config flag"
```

---

## Task 5: Prompts + Resources — `memory_curation_directive`

**Files:**
- Modify: `mcp_agents_registry/prompts.py`
- Modify: `mcp_agents_registry/resources.py`
- Modify: `mcp_agents_registry/server.py`

- [ ] **Step 1: Edit `mcp_agents_registry/prompts.py`**

Append this function:

```python
def memory_curation_directive() -> str:
    return (
        "SYSTEM DIRECTIVE: When you resolve a complex bug or establish a new rule, "
        "DO NOT assume it should be saved. Ask the user: "
        "'Should I add this to the project\\'s AGENTS.md?' "
        "If the user agrees, use the `propose_registry_update` tool. "
        "Do not use direct file write tools."
    )
```

- [ ] **Step 2: Edit `mcp_agents_registry/resources.py`**

Add this import at the top alongside the existing import:

```python
from .proposals import MemoryProposal
```

Add this function at the end of the file:

```python
def proposals_resource_payload(registry: AgentsRegistry) -> str:
    proposals = registry.list_proposals()
    return to_pretty_json({"proposals": [p.to_dict() for p in proposals]})
```

- [ ] **Step 3: Edit `mcp_agents_registry/server.py`**

Add the import of the new helpers at the top of the file alongside the existing imports:

```python
from .prompts import build_project_prompt, build_resolve_context_prompt, memory_curation_directive
from .resources import (
    ...existing imports...,
    proposals_resource_payload,
)
```

Inside `create_server`, add the resource and prompt registration after the existing `agents://managed-files` resource:

```python
    @app.resource("agents://directives/memory-curation")
    def memory_curation_resource() -> str:
        return memory_curation_directive()

    if hasattr(app, "prompt"):
        # extend the existing prompt block — add inside it:
        @app.prompt()
        def memory_curation() -> str:
            return memory_curation_directive()
```

(The `memory_curation` prompt registration must go inside the existing `if hasattr(app, "prompt"):` block alongside the other two prompts.)

- [ ] **Step 4: Run the full suite**

```bash
uv run pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_agents_registry/prompts.py mcp_agents_registry/resources.py mcp_agents_registry/server.py
git commit -m "feat: add memory_curation_directive prompt and resource"
```

---

## Task 6: Web API — 4 proposal routes

**Files:**
- Modify: `mcp_agents_registry/web.py`
- Create: `tests/test_web_proposals.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_web_proposals.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from mcp_agents_registry.web import create_web_app
except Exception as exc:
    TestClient = None
    create_web_app = None
    WEB_IMPORT_ERROR = exc
else:
    WEB_IMPORT_ERROR = None


def _make_app_and_client(temp_dir: str):
    root = Path(temp_dir) / "ws"
    root.mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# Purpose\nTest workspace\n", encoding="utf-8")
    config_path = Path(temp_dir) / "config.yaml"
    config_path.write_text(
        f"roots:\n  - {root}\ncache_enabled: false\nparse_sections: true\n",
        encoding="utf-8",
    )
    app = create_web_app(str(config_path))
    return app, TestClient(app)


class ProposalWebTests(unittest.TestCase):
    def setUp(self) -> None:
        if WEB_IMPORT_ERROR is not None or TestClient is None or create_web_app is None:
            self.skipTest(f"Web test dependencies missing: {WEB_IMPORT_ERROR}")
        self._tmp = tempfile.TemporaryDirectory()
        self.app, self.client = _make_app_and_client(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _project_name(self) -> str:
        return self.client.get("/api/projects").json()["projects"][0]["project_name"]

    def _add_proposal(self) -> dict:
        project_name = self._project_name()
        resp = self.client.post("/api/proposals", json={
            "target_project": project_name,
            "section_heading": "Notes",
            "proposed_content": "- a note\n",
            "rationale": "test rationale",
        })
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_get_proposals_returns_empty_list_initially(self) -> None:
        resp = self.client.get("/api/proposals")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["proposals"], [])

    def test_get_proposals_filters_by_status(self) -> None:
        self._add_proposal()
        resp = self.client.get("/api/proposals?status=pending")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["proposals"]), 1)

    def test_post_proposal_creates_pending_entry(self) -> None:
        result = self._add_proposal()
        self.assertIn("proposal_id", result)
        self.assertEqual(result["status"], "pending")

    def test_post_proposal_unknown_project_returns_400(self) -> None:
        resp = self.client.post("/api/proposals", json={
            "target_project": "nonexistent",
            "section_heading": "Notes",
            "proposed_content": "x",
            "rationale": "r",
        })
        self.assertEqual(resp.status_code, 400)

    def test_approve_proposal_returns_approved_status(self) -> None:
        proposal_id = self._add_proposal()["proposal_id"]
        resp = self.client.post(f"/api/proposals/{proposal_id}/approve")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "approved")

    def test_approve_unknown_id_returns_404(self) -> None:
        resp = self.client.post("/api/proposals/no-such-id/approve")
        self.assertEqual(resp.status_code, 404)

    def test_reject_proposal_returns_rejected_status(self) -> None:
        proposal_id = self._add_proposal()["proposal_id"]
        resp = self.client.post(f"/api/proposals/{proposal_id}/reject")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "rejected")

    def test_patch_proposal_updates_content(self) -> None:
        proposal_id = self._add_proposal()["proposal_id"]
        resp = self.client.patch(f"/api/proposals/{proposal_id}", json={
            "proposed_content": "- edited note\n",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["proposed_content"], "- edited note\n")

    def test_patch_proposal_unknown_id_returns_404(self) -> None:
        resp = self.client.patch("/api/proposals/no-such-id", json={"proposed_content": "x"})
        self.assertEqual(resp.status_code, 404)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_web_proposals.py -v
```
Expected: `404 Not Found` for `/api/proposals`.

- [ ] **Step 3: Edit `mcp_agents_registry/web.py`**

Add these routes inside `create_web_app`, after the existing `/api/refresh` route:

```python
    @app.get("/api/proposals")
    def list_proposals(status: str | None = None) -> dict[str, object]:
        proposals = registry.list_proposals(status=status)
        return {"proposals": [p.to_dict() for p in proposals]}

    @app.post("/api/proposals")
    def create_proposal(payload: dict[str, object]) -> dict[str, object]:
        try:
            return _propose_registry_update(
                registry=registry,
                target_project=str(payload.get("target_project", "")),
                section_heading=str(payload.get("section_heading", "")),
                proposed_content=str(payload.get("proposed_content", "")),
                rationale=str(payload.get("rationale", "")),
                agent_id=str(payload.get("agent_id", "")),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/proposals/{proposal_id}/approve")
    def approve_proposal(proposal_id: str) -> dict[str, object]:
        try:
            return registry.approve_proposal(proposal_id).to_dict()
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/proposals/{proposal_id}/reject")
    def reject_proposal(proposal_id: str) -> dict[str, object]:
        try:
            return registry.reject_proposal(proposal_id).to_dict()
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/proposals/{proposal_id}")
    def edit_proposal(proposal_id: str, payload: dict[str, object]) -> dict[str, object]:
        try:
            return registry.edit_proposal(
                proposal_id,
                proposed_content=str(payload["proposed_content"]) if "proposed_content" in payload else None,
                section_heading=str(payload["section_heading"]) if "section_heading" in payload else None,
            ).to_dict()
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
```

Also add the import of `_propose_registry_update` at the top of `web.py`:

```python
from .server import _propose_registry_update
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/test_web_proposals.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_agents_registry/web.py tests/test_web_proposals.py
git commit -m "feat: add /api/proposals CRUD routes to web admin"
```

---

## Task 7: Frontend — Review Queue panel

**Files:**
- Modify: `mcp_agents_registry/web_assets/templates/admin.html`
- Modify: `mcp_agents_registry/web_assets/static/app.js`

- [ ] **Step 1: Add nav item + panel to `admin.html`**

In the `<aside class="sidenav">` block, add after the `<a href="#sec-editor"...>` line:

```html
      <a href="#sec-proposals" class="nav-item" id="nav-proposals">
        <span class="num">06</span>
        <span>Review Queue</span>
        <span class="badge" id="proposalBadge" style="display:none"></span>
      </a>
```

Add the panel before the closing `</main>` tag:

```html
    <section id="sec-proposals" class="panel">
      <header class="panel-head">
        <div class="panel-title">
          <span class="panel-num">06</span>
          <h2>Review Queue</h2>
        </div>
        <span class="panel-tag">Memory proposals</span>
      </header>
      <div class="panel-body">
        <div class="toolbar">
          <label>
            <input type="checkbox" id="showHistory" />
            Show approved/rejected history
          </label>
        </div>
        <ul id="proposalList" class="item-list"></ul>
        <p id="proposalEmpty" style="display:none; color: var(--fg-muted);">No pending proposals.</p>
      </div>
    </section>
```

- [ ] **Step 2: Add proposal JS to `app.js`**

Append this block to the end of `app.js`:

```js
// ── Review Queue ──────────────────────────────────────────────

const proposalListNode = document.getElementById('proposalList');
const proposalEmptyNode = document.getElementById('proposalEmpty');
const proposalBadgeNode = document.getElementById('proposalBadge');
const showHistoryNode = document.getElementById('showHistory');

function renderProposals(proposals) {
  proposalListNode.innerHTML = '';
  if (proposals.length === 0) {
    proposalEmptyNode.style.display = '';
    return;
  }
  proposalEmptyNode.style.display = 'none';
  for (const p of proposals) {
    const li = document.createElement('li');
    li.className = 'card';
    li.dataset.id = p.id;
    const isPending = p.status === 'pending';
    li.innerHTML = `
      <div class="card-head">
        <span class="pill">${escapeHtml(p.target_project)}</span>
        <span class="pill mono-small">${escapeHtml(p.section_heading)}</span>
        ${p.agent_id ? `<span class="pill">agent: ${escapeHtml(p.agent_id)}</span>` : ''}
        <span class="pill pill-status pill-${p.status}">${p.status}</span>
      </div>
      <p class="card-rationale"><em>${escapeHtml(p.rationale)}</em></p>
      ${isPending ? `
        <label class="field-label">Section heading</label>
        <input class="input-heading" type="text" value="${escapeHtml(p.section_heading)}" />
        <label class="field-label">Content</label>
        <textarea class="input-content" rows="6">${escapeHtml(p.proposed_content)}</textarea>
        <div class="card-actions">
          <button class="btn btn-primary btn-approve">Approve</button>
          <button class="btn btn-danger btn-reject">Reject</button>
        </div>
      ` : ''}
    `;
    if (isPending) {
      li.querySelector('.btn-approve').addEventListener('click', () => approveProposal(p.id, li));
      li.querySelector('.btn-reject').addEventListener('click', () => rejectProposal(p.id, li));
      const contentArea = li.querySelector('.input-content');
      const headingInput = li.querySelector('.input-heading');
      contentArea.addEventListener('blur', () => saveProposalEdits(p.id, headingInput.value, contentArea.value));
      headingInput.addEventListener('blur', () => saveProposalEdits(p.id, headingInput.value, contentArea.value));
    }
    proposalListNode.appendChild(li);
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function loadProposals() {
  try {
    const showHistory = showHistoryNode && showHistoryNode.checked;
    const url = showHistory ? '/api/proposals' : '/api/proposals?status=pending';
    const data = await callApi(url);
    renderProposals(data.proposals || []);
    updateProposalBadge(data.proposals ? data.proposals.filter(p => p.status === 'pending').length : 0);
  } catch (err) {
    setStatus('Error loading proposals: ' + err.message);
  }
}

function updateProposalBadge(count) {
  if (!proposalBadgeNode) return;
  if (count > 0) {
    proposalBadgeNode.textContent = count;
    proposalBadgeNode.style.display = '';
  } else {
    proposalBadgeNode.style.display = 'none';
  }
}

async function approveProposal(id, liNode) {
  try {
    await callApi(`/api/proposals/${id}/approve`, { method: 'POST' });
    liNode.remove();
    await loadProposals();
  } catch (err) {
    setStatus('Approve failed: ' + err.message);
  }
}

async function rejectProposal(id, liNode) {
  try {
    await callApi(`/api/proposals/${id}/reject`, { method: 'POST' });
    liNode.remove();
    await loadProposals();
  } catch (err) {
    setStatus('Reject failed: ' + err.message);
  }
}

async function saveProposalEdits(id, sectionHeading, proposedContent) {
  try {
    await callApi(`/api/proposals/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_heading: sectionHeading, proposed_content: proposedContent }),
    });
  } catch (err) {
    setStatus('Auto-save failed: ' + err.message);
  }
}

if (showHistoryNode) {
  showHistoryNode.addEventListener('change', loadProposals);
}

loadProposals();
```

- [ ] **Step 3: Add minimal CSS for new elements to `styles.css`**

Append to `mcp_agents_registry/web_assets/static/styles.css`:

```css
/* Review Queue */
.card { background: var(--bg-card, var(--bg-panel)); border: 1px solid var(--border); border-radius: 6px; padding: 16px; margin-bottom: 12px; }
.card-head { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }
.card-rationale { margin: 0 0 10px; font-size: 0.9em; color: var(--fg-muted, #888); }
.card-actions { display: flex; gap: 8px; margin-top: 10px; }
.field-label { display: block; font-size: 0.8em; font-weight: 600; color: var(--fg-muted, #888); margin: 8px 0 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.input-heading { width: 100%; padding: 4px 8px; font-size: 0.9em; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-input, var(--bg-panel)); color: var(--fg); }
.input-content { width: 100%; padding: 6px 8px; font-family: monospace; font-size: 0.85em; border: 1px solid var(--border); border-radius: 4px; resize: vertical; background: var(--bg-input, var(--bg-panel)); color: var(--fg); }
.pill-approved { background: var(--green-muted, #d1fae5); color: var(--green-text, #065f46); }
.pill-rejected { background: var(--red-muted, #fee2e2); color: var(--red-text, #991b1b); }
.pill-pending { background: var(--blue-muted, #dbeafe); color: var(--blue-text, #1e40af); }
.badge { display: inline-block; background: #ef4444; color: #fff; border-radius: 10px; font-size: 0.7em; font-weight: 700; padding: 1px 6px; margin-left: 4px; vertical-align: middle; }
.btn-danger { background: var(--red-muted, #fee2e2); color: var(--red-text, #991b1b); border: 1px solid var(--red-text, #991b1b); }
```

- [ ] **Step 4: Start the web server and verify the UI manually**

```bash
AGENTS_REGISTRY_CONFIG=config.yaml uv run mcp-agents-registry-web
```

Navigate to `http://127.0.0.1:8002`. Verify:
- Nav item "06 Review Queue" appears in the sidebar.
- Clicking it scrolls to the panel.
- "No pending proposals." message shows (list is empty).
- The badge is hidden when no proposals exist.

Stop the server with Ctrl-C.

- [ ] **Step 5: Run the full suite one final time**

```bash
uv run pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_agents_registry/web_assets/templates/admin.html mcp_agents_registry/web_assets/static/app.js mcp_agents_registry/web_assets/static/styles.css
git commit -m "feat: add Review Queue panel to admin UI with proposal cards"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task |
|---|---|
| `MemoryProposal` dataclass | Task 1 |
| `ProposalStore` CRUD | Task 1 |
| `allow_direct_writes` config | Task 2 |
| `proposals_path` config | Task 2 |
| Registry delegating methods | Task 3 |
| `approve_proposal` writes + refreshes | Task 3 (uses `update_managed_file_section` which calls `refresh_index` internally) |
| `propose_registry_update` MCP tool | Task 4 |
| Gate direct-write tools | Task 4 |
| `memory_curation_directive` prompt + resource | Task 5 |
| 4 web API routes | Task 6 |
| Review Queue nav + panel | Task 7 |
| Proposal cards (target badge, rationale, editable textarea, buttons) | Task 7 |
| Badge with pending count | Task 7 |
| History toggle | Task 7 |

All spec requirements covered. No TBDs or placeholders. Types and method names are consistent across tasks (`add_proposal`, `list_proposals`, `approve_proposal`, `reject_proposal`, `edit_proposal` used identically in Tasks 3, 4, 6). `_propose_registry_update` defined in Task 4 and imported in Task 6.
