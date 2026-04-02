from __future__ import annotations

import os
from typing import Any

from .prompts import build_project_prompt, build_resolve_context_prompt
from .registry import AgentsRegistry
from .resources import (
    account_inventory_resource_payload,
    device_inventory_resource_payload,
    inventory_resource_payload,
    managed_files_resource_payload,
    path_resource_payload,
    project_effective_resource_payload,
    project_raw_resource_payload,
    project_resource_payload,
    projects_resource_payload,
)


def create_server(config_path: str | None = None) -> Any:
    FastMCP = _load_fastmcp()
    resolved_config_path = config_path or os.environ.get("AGENTS_REGISTRY_CONFIG", "config.yaml")
    registry = AgentsRegistry.from_config_path(resolved_config_path)
    registry.refresh_index()

    app = FastMCP(name="Agents Registry")

    @app.tool()
    def list_projects() -> dict[str, object]:
        return {"projects": registry.list_projects()}

    @app.tool()
    def get_project(project_name: str) -> dict[str, object]:
        return registry.get_project(project_name)

    @app.tool()
    def resolve_context(path: str) -> dict[str, object]:
        return registry.resolve_context(path)

    @app.tool()
    def search_projects(query: str) -> dict[str, object]:
        return registry.search_projects(query)

    @app.tool()
    def refresh_index() -> dict[str, int]:
        return registry.refresh_index().to_dict()

    @app.tool()
    def list_accounts() -> dict[str, object]:
        return {"accounts": registry.list_accounts()}

    @app.tool()
    def create_account(
        account_id: str,
        display_name: str,
        provider: str = "",
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        return registry.create_account(
            account_id=account_id,
            display_name=display_name,
            provider=provider,
            metadata=metadata,
            tags=tags,
        )

    @app.tool()
    def update_account(
        account_id: str,
        display_name: str | None = None,
        provider: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        return registry.update_account(
            account_id=account_id,
            display_name=display_name,
            provider=provider,
            metadata=metadata,
            tags=tags,
        )

    @app.tool()
    def delete_account(account_id: str) -> dict[str, object]:
        return registry.delete_account(account_id)

    @app.tool()
    def list_devices() -> dict[str, object]:
        return {"devices": registry.list_devices()}

    @app.tool()
    def create_device(
        device_id: str,
        display_name: str,
        platform: str = "",
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        return registry.create_device(
            device_id=device_id,
            display_name=display_name,
            platform=platform,
            metadata=metadata,
            tags=tags,
        )

    @app.tool()
    def update_device(
        device_id: str,
        display_name: str | None = None,
        platform: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        return registry.update_device(
            device_id=device_id,
            display_name=display_name,
            platform=platform,
            metadata=metadata,
            tags=tags,
        )

    @app.tool()
    def delete_device(device_id: str) -> dict[str, object]:
        return registry.delete_device(device_id)

    @app.tool()
    def list_installations(
        account_id: str = "",
        device_id: str = "",
        agent_name: str = "",
        skill: str = "",
    ) -> dict[str, object]:
        return {
            "installations": registry.list_installations(
                account_id=account_id or None,
                device_id=device_id or None,
                agent_name=agent_name or None,
                skill=skill or None,
            )
        }

    @app.tool()
    def assign_agent_installation(
        account_id: str,
        device_id: str,
        agent_name: str,
        skills: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, object]:
        return registry.assign_agent_installation(
            account_id=account_id,
            device_id=device_id,
            agent_name=agent_name,
            skills=skills,
            notes=notes,
        )

    @app.tool()
    def remove_agent_installation(account_id: str, device_id: str, agent_name: str) -> dict[str, object]:
        return registry.remove_agent_installation(
            account_id=account_id,
            device_id=device_id,
            agent_name=agent_name,
        )

    @app.tool()
    def where_is_agent_installed(agent_name: str) -> dict[str, object]:
        return registry.where_is_agent_installed(agent_name)

    @app.tool()
    def skills_for_account_device(account_id: str, device_id: str) -> dict[str, object]:
        return registry.skills_for_account_device(account_id, device_id)

    @app.tool()
    def inventory_coverage() -> dict[str, object]:
        return registry.inventory_coverage()

    @app.tool()
    def search_inventory(
        account_id: str = "",
        device_id: str = "",
        agent_name: str = "",
        skill: str = "",
        path: str = "",
    ) -> dict[str, object]:
        return registry.search_inventory(
            account_id=account_id,
            device_id=device_id,
            agent_name=agent_name,
            skill=skill,
            path=path,
        )

    @app.tool()
    def list_managed_files(path_query: str = "") -> dict[str, object]:
        return {"files": registry.list_managed_files(path_query=path_query)}

    @app.tool()
    def read_managed_file(path: str) -> dict[str, object]:
        return registry.read_managed_file(path)

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

    @app.resource("agents://projects")
    def projects_resource() -> str:
        return projects_resource_payload(registry)

    @app.resource("agents://project/{project_name}")
    def project_resource(project_name: str) -> str:
        return project_resource_payload(registry, project_name)

    @app.resource("agents://project/{project_name}/raw")
    def project_raw_resource(project_name: str) -> str:
        return project_raw_resource_payload(registry, project_name)

    @app.resource("agents://project/{project_name}/effective")
    def project_effective_resource(project_name: str) -> str:
        return project_effective_resource_payload(registry, project_name)

    @app.resource("agents://path/{encoded_path}")
    def path_resource(encoded_path: str) -> str:
        return path_resource_payload(registry, encoded_path)

    @app.resource("agents://inventory")
    def inventory_resource() -> str:
        return inventory_resource_payload(registry)

    @app.resource("agents://inventory/account/{account_id}")
    def account_inventory_resource(account_id: str) -> str:
        return account_inventory_resource_payload(registry, account_id)

    @app.resource("agents://inventory/device/{device_id}")
    def device_inventory_resource(device_id: str) -> str:
        return device_inventory_resource_payload(registry, device_id)

    @app.resource("agents://managed-files")
    def managed_files_resource() -> str:
        return managed_files_resource_payload(registry)

    if hasattr(app, "prompt"):
        @app.prompt()
        def explain_path_context(path: str) -> str:
            return build_resolve_context_prompt(path)

        @app.prompt()
        def summarize_project(project_name: str) -> str:
            return build_project_prompt(project_name)

    return app


def _load_fastmcp() -> type[Any]:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP Python SDK is not installed. Install project dependencies before running the server."
        ) from exc
    return FastMCP


def main() -> None:
    app = create_server()
    app.run()


if __name__ == "__main__":
    main()
