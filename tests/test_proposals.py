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

    def test_update_rejects_immutable_fields(self) -> None:
        p = self.store.add(target_project="a", target_path="/a/AGENTS.md",
                           section_heading="S", proposed_content="c", rationale="r")
        with self.assertRaises(ValueError):
            self.store.update(p.id, id="hacked", status="approved")

    def test_none_path_store_is_a_noop(self) -> None:
        store = ProposalStore(None)
        store.add(target_project="a", target_path="/a/AGENTS.md",
                  section_heading="S", proposed_content="c", rationale="r")
        self.assertEqual(store.load(), [])


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

    def test_approve_proposal_raises_for_already_approved(self) -> None:
        p = self.registry.add_proposal(
            target_project=self.project_name, target_path=self.target_path,
            section_heading="S", proposed_content="c", rationale="r",
        )
        self.registry.approve_proposal(p.id)
        with self.assertRaises(ValueError):
            self.registry.approve_proposal(p.id)

    def test_reject_proposal_raises_for_already_rejected(self) -> None:
        p = self.registry.add_proposal(
            target_project=self.project_name, target_path=self.target_path,
            section_heading="S", proposed_content="c", rationale="r",
        )
        self.registry.reject_proposal(p.id)
        with self.assertRaises(ValueError):
            self.registry.reject_proposal(p.id)


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
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "AGENTS.md").write_text("# Purpose\nTest\n", encoding="utf-8")
            config_path = root / "config.yaml"
            config_path.write_text(
                f"roots:\n  - {root}\ncache_enabled: false\nallow_direct_writes: false\n",
                encoding="utf-8",
            )
            from mcp_agents_registry.server import create_server
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
