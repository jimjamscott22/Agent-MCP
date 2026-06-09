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

    def test_approve_already_approved_returns_400(self) -> None:
        proposal_id = self._add_proposal()["proposal_id"]
        self.client.post(f"/api/proposals/{proposal_id}/approve")
        resp = self.client.post(f"/api/proposals/{proposal_id}/approve")
        self.assertEqual(resp.status_code, 400)

    def test_reject_already_rejected_returns_400(self) -> None:
        proposal_id = self._add_proposal()["proposal_id"]
        self.client.post(f"/api/proposals/{proposal_id}/reject")
        resp = self.client.post(f"/api/proposals/{proposal_id}/reject")
        self.assertEqual(resp.status_code, 400)
