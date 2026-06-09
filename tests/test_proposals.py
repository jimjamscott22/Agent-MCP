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
