from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import mcp_agents_registry.web as web

try:
    from fastapi.testclient import TestClient
    from mcp_agents_registry.web import create_web_app
except Exception as exc:  # pragma: no cover - test skip path
    TestClient = None
    create_web_app = None
    WEB_IMPORT_ERROR = exc
else:
    WEB_IMPORT_ERROR = None


class WebApiTests(unittest.TestCase):
    def test_admin_cli_defaults_to_port_8002(self) -> None:
        uvicorn = Mock()
        app = object()

        with (
            patch("sys.argv", ["mcp-agents-registry-web"]),
            patch.object(web, "_load_uvicorn", return_value=uvicorn),
            patch.object(web, "create_web_app", return_value=app),
        ):
            web.main()

        uvicorn.run.assert_called_once_with(app, host="127.0.0.1", port=8002)

    def test_health_projects_and_context_endpoints(self) -> None:
        if WEB_IMPORT_ERROR is not None or TestClient is None or create_web_app is None:
            self.skipTest(f"Web test dependencies are missing: {WEB_IMPORT_ERROR}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            project = root / "project"
            project.mkdir(parents=True, exist_ok=True)
            (root / "AGENTS.md").write_text("# Purpose\nWorkspace defaults\n", encoding="utf-8")
            (project / "AGENTS.md").write_text("# Purpose\nProject app\n", encoding="utf-8")

            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "roots:",
                        f"  - {root}",
                        "cache_enabled: false",
                        "parse_sections: true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            app = create_web_app(str(config_path))
            with TestClient(app) as client:
                health = client.get("/api/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["status"], "ok")

                projects = client.get("/api/projects")
                self.assertEqual(projects.status_code, 200)
                payload = projects.json()["projects"]
                self.assertEqual(len(payload), 2)

                project_name = payload[0]["project_name"]
                by_name = client.get(f"/api/projects/{project_name}")
                self.assertEqual(by_name.status_code, 200)
                self.assertEqual(by_name.json()["project_name"], project_name)

                missing = client.get("/api/projects/not-real")
                self.assertEqual(missing.status_code, 404)

                target_path = str(project / "src" / "main.py")
                context = client.get("/api/context", params={"path": target_path})
                self.assertEqual(context.status_code, 200)
                self.assertEqual(len(context.json()["matched_agent_files"]), 2)

                outside_context = client.get("/api/context", params={"path": str(Path(temp_dir) / "outside.py")})
                self.assertEqual(outside_context.status_code, 400)

    def test_inventory_endpoints_round_trip(self) -> None:
        if WEB_IMPORT_ERROR is not None or TestClient is None or create_web_app is None:
            self.skipTest(f"Web test dependencies are missing: {WEB_IMPORT_ERROR}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            root.mkdir(parents=True, exist_ok=True)
            (root / "AGENTS.md").write_text("# Purpose\nWorkspace defaults\n", encoding="utf-8")

            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "roots:",
                        f"  - {root}",
                        "cache_enabled: false",
                        "parse_sections: true",
                        "inventory_path: .cache/test_inventory.json",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            app = create_web_app(str(config_path))
            with TestClient(app) as client:
                account = client.post(
                    "/api/accounts",
                    json={
                        "account_id": "acct-main",
                        "display_name": "Main",
                        "provider": "claude",
                    },
                )
                self.assertEqual(account.status_code, 200)

                device = client.post(
                    "/api/devices",
                    json={
                        "device_id": "dev-laptop",
                        "display_name": "Laptop",
                        "platform": "linux",
                    },
                )
                self.assertEqual(device.status_code, 200)

                install = client.post(
                    "/api/installations",
                    json={
                        "account_id": "acct-main",
                        "device_id": "dev-laptop",
                        "agent_name": "Copilot",
                        "skills": ["python", "mcp", "python"],
                    },
                )
                self.assertEqual(install.status_code, 200)
                self.assertEqual(install.json()["skills"], ["python", "mcp"])

                where_agent = client.get("/api/inventory/where-agent", params={"agent_name": "Copilot"})
                self.assertEqual(where_agent.status_code, 200)
                self.assertEqual(len(where_agent.json()["installations"]), 1)

                skills = client.get(
                    "/api/inventory/skills",
                    params={
                        "account_id": "acct-main",
                        "device_id": "dev-laptop",
                    },
                )
                self.assertEqual(skills.status_code, 200)
                self.assertEqual(skills.json()["skills"], ["python", "mcp"])


if __name__ == "__main__":
    unittest.main()
