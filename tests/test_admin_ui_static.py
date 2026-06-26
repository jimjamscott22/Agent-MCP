from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AdminUiStaticTests(unittest.TestCase):
    def test_admin_template_exposes_control_console_panels(self) -> None:
        html = (ROOT / "mcp_agents_registry" / "web_assets" / "templates" / "admin.html").read_text(encoding="utf-8")

        required_ids = [
            "adminState",
            "projectDetails",
            "accountsTableBody",
            "devicesTableBody",
            "installationsTableBody",
            "skillsOverview",
            "inventorySearchBtn",
            "proposalProject",
            "proposalSection",
            "proposalContent",
            "sectionHeadingInput",
            "sectionContentInput",
            "writeSectionBtn",
            "confirmModal",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', html)

    def test_admin_script_wires_new_console_actions(self) -> None:
        script = (ROOT / "mcp_agents_registry" / "web_assets" / "static" / "app.js").read_text(encoding="utf-8")

        required_functions = [
            "loadAdminState",
            "renderProjectDetails",
            "renderInventoryTables",
            "searchInventory",
            "deleteAccount",
            "deleteDevice",
            "removeInstallation",
            "createProposal",
            "saveManagedFileSection",
            "previewDiff",
            "confirmAction",
        ]
        for function_name in required_functions:
            self.assertIn(f"function {function_name}", script)
