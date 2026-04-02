from __future__ import annotations

from .registry import AgentsRegistry
from .utils import decode_resource_path, to_pretty_json


def projects_resource_payload(registry: AgentsRegistry) -> str:
    return to_pretty_json({"projects": registry.list_projects()})


def project_resource_payload(registry: AgentsRegistry, project_name: str) -> str:
    return to_pretty_json(registry.get_project(project_name))


def project_raw_resource_payload(registry: AgentsRegistry, project_name: str) -> str:
    return registry.get_project_record(project_name).raw_markdown


def project_effective_resource_payload(registry: AgentsRegistry, project_name: str) -> str:
    return to_pretty_json(registry.resolve_project_root(project_name))


def path_resource_payload(registry: AgentsRegistry, encoded_path: str) -> str:
    return to_pretty_json(registry.resolve_context(decode_resource_path(encoded_path)))


def inventory_resource_payload(registry: AgentsRegistry) -> str:
    return to_pretty_json(
        {
            "accounts": registry.list_accounts(),
            "devices": registry.list_devices(),
            "installations": registry.list_installations(),
            "coverage": registry.inventory_coverage(),
        }
    )


def account_inventory_resource_payload(registry: AgentsRegistry, account_id: str) -> str:
    return to_pretty_json(
        {
            "account_id": account_id,
            "installations": registry.list_installations(account_id=account_id),
        }
    )


def device_inventory_resource_payload(registry: AgentsRegistry, device_id: str) -> str:
    return to_pretty_json(
        {
            "device_id": device_id,
            "installations": registry.list_installations(device_id=device_id),
        }
    )


def managed_files_resource_payload(registry: AgentsRegistry) -> str:
    return to_pretty_json({"files": registry.list_managed_files()})
