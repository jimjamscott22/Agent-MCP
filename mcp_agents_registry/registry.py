from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from .cache import RegistryCache
from .config import AppConfig, load_config
from .inventory_store import InventoryStore
from .models import (
    AccountRecord,
    CacheEntry,
    DeviceRecord,
    InventorySnapshot,
    InstallationRecord,
    ManagedFileRecord,
    ParsedAgentContent,
    ProjectRecord,
    RefreshSummary,
)
from .parser import parse_agent_markdown
from .resolver import ContextResolver
from .scanner import scan_agent_files
from .utils import compact_text, ensure_within_roots, normalize_path, read_text_file, sha256_file, unique_preserving_order


class AgentsRegistry:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.cache = RegistryCache(config.cache_path if config.cache_enabled else None)
        self.inventory_store = InventoryStore(config.inventory_path)
        self.accounts: dict[str, AccountRecord] = {}
        self.devices: dict[str, DeviceRecord] = {}
        self.installations: list[InstallationRecord] = []
        self._load_inventory()
        self.resolver = ContextResolver(config)
        self.projects: list[ProjectRecord] = []
        self.projects_by_name: dict[str, ProjectRecord] = {}

    @classmethod
    def from_config_path(cls, config_path: str | Path) -> "AgentsRegistry":
        return cls(load_config(config_path))

    def refresh_index(self) -> RefreshSummary:
        cached_entries = self.cache.load() if self.config.cache_enabled else {}
        previous_signatures = _build_previous_signatures(self.projects, cached_entries)
        discovered = scan_agent_files(self.config)

        records_without_names: list[ProjectRecord] = []
        current_cache: dict[str, CacheEntry] = {}
        added = 0
        changed = 0

        for discovered_file in discovered:
            cached = cached_entries.get(discovered_file.agent_file_path)
            use_cached = bool(
                cached
                and cached.sha256 == discovered_file.sha256
                and cached.file_size == discovered_file.file_size
                and cached.mtime == discovered_file.mtime
            )
            if use_cached:
                raw_markdown = cached.raw_markdown
                parsed_content = cached.parsed_content
            else:
                try:
                    raw_markdown = read_text_file(Path(discovered_file.agent_file_path))
                except OSError:
                    continue
                parsed_content = parse_agent_markdown(raw_markdown) if self.config.parse_sections else ParsedAgentContent(summary=compact_text(raw_markdown))

            previous_signature = previous_signatures.get(discovered_file.agent_file_path)
            if previous_signature is None:
                added += 1
            elif previous_signature != (discovered_file.sha256, discovered_file.file_size, discovered_file.mtime):
                changed += 1

            current_cache[discovered_file.agent_file_path] = CacheEntry(
                agent_file_path=discovered_file.agent_file_path,
                mtime=discovered_file.mtime,
                sha256=discovered_file.sha256,
                file_size=discovered_file.file_size,
                raw_markdown=raw_markdown,
                parsed_content=parsed_content,
            )
            records_without_names.append(
                ProjectRecord(
                    project_name="",
                    agent_file_path=discovered_file.agent_file_path,
                    project_root=discovered_file.project_root,
                    scan_root=discovered_file.scan_root,
                    relative_root_from_scan_base=discovered_file.relative_root_from_scan_base,
                    parent_project_name=None,
                    depth=discovered_file.depth,
                    raw_markdown=raw_markdown,
                    parsed_sections=parsed_content,
                    tags=parsed_content.tags,
                    summary=parsed_content.summary,
                    mtime=discovered_file.mtime,
                    sha256=discovered_file.sha256,
                    file_size=discovered_file.file_size,
                )
            )

        removed = len(set(previous_signatures) - {item.agent_file_path for item in discovered})
        named_records = _assign_project_names(records_without_names)
        _assign_relationships(named_records)
        named_records.sort(key=lambda record: (record.project_name.casefold(), record.project_root))

        self.projects = named_records
        self.projects_by_name = {project.project_name: project for project in named_records}
        if self.config.cache_enabled:
            self.cache.save(current_cache)
        return RefreshSummary(
            project_count=len(named_records),
            added=added,
            changed=changed,
            removed=removed,
        )

    def list_projects(self) -> list[dict[str, Any]]:
        return [project.to_dict() for project in self.projects]

    def get_project(self, project_name: str) -> dict[str, Any]:
        project = self.projects_by_name.get(project_name)
        if project is None:
            raise LookupError(f"Unknown project: {project_name}")
        return project.to_dict()

    def get_project_record(self, project_name: str) -> ProjectRecord:
        project = self.projects_by_name.get(project_name)
        if project is None:
            raise LookupError(f"Unknown project: {project_name}")
        return project

    def resolve_context(self, path: str | Path) -> dict[str, Any]:
        return self.resolver.resolve(path, self.projects).to_dict()

    def resolve_project_root(self, project_name: str) -> dict[str, Any]:
        project = self.get_project_record(project_name)
        return self.resolve_context(project.project_root)

    def search_projects(self, query: str) -> dict[str, Any]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return {"query": query, "matches": []}

        scored: list[tuple[int, ProjectRecord]] = []
        for project in self.projects:
            score = _score_project(project, terms)
            if score > 0:
                scored.append((score, project))
        scored.sort(key=lambda item: (-item[0], item[1].project_name.casefold(), item[1].project_root))
        return {
            "query": query,
            "matches": [
                {
                    "score": score,
                    **project.to_dict(),
                }
                for score, project in scored
            ],
        }

    def list_accounts(self) -> list[dict[str, Any]]:
        return [account.to_dict() for account in sorted(self.accounts.values(), key=lambda item: item.account_id.casefold())]

    def create_account(
        self,
        account_id: str,
        display_name: str,
        *,
        provider: str = "",
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        key = account_id.strip()
        if not key:
            raise ValueError("account_id is required.")
        if key in self.accounts:
            raise ValueError(f"Account already exists: {key}")
        if not display_name.strip():
            raise ValueError("display_name is required.")
        self.accounts[key] = AccountRecord(
            account_id=key,
            display_name=display_name.strip(),
            provider=provider.strip(),
            metadata={str(name): str(value) for name, value in (metadata or {}).items()},
            tags=unique_preserving_order([str(tag).strip() for tag in (tags or []) if str(tag).strip()]),
        )
        self._save_inventory()
        return self.accounts[key].to_dict()

    def update_account(
        self,
        account_id: str,
        *,
        display_name: str | None = None,
        provider: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        account = self.accounts.get(account_id)
        if account is None:
            raise LookupError(f"Unknown account: {account_id}")
        if display_name is not None:
            if not display_name.strip():
                raise ValueError("display_name cannot be empty.")
            account.display_name = display_name.strip()
        if provider is not None:
            account.provider = provider.strip()
        if metadata is not None:
            account.metadata = {str(name): str(value) for name, value in metadata.items()}
        if tags is not None:
            account.tags = unique_preserving_order([str(tag).strip() for tag in tags if str(tag).strip()])
        self._save_inventory()
        return account.to_dict()

    def delete_account(self, account_id: str) -> dict[str, Any]:
        if account_id not in self.accounts:
            raise LookupError(f"Unknown account: {account_id}")
        del self.accounts[account_id]
        removed_installations = len([item for item in self.installations if item.account_id == account_id])
        self.installations = [item for item in self.installations if item.account_id != account_id]
        self._save_inventory()
        return {"account_id": account_id, "removed_installations": removed_installations}

    def list_devices(self) -> list[dict[str, Any]]:
        return [device.to_dict() for device in sorted(self.devices.values(), key=lambda item: item.device_id.casefold())]

    def create_device(
        self,
        device_id: str,
        display_name: str,
        *,
        platform: str = "",
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        key = device_id.strip()
        if not key:
            raise ValueError("device_id is required.")
        if key in self.devices:
            raise ValueError(f"Device already exists: {key}")
        if not display_name.strip():
            raise ValueError("display_name is required.")
        self.devices[key] = DeviceRecord(
            device_id=key,
            display_name=display_name.strip(),
            platform=platform.strip(),
            metadata={str(name): str(value) for name, value in (metadata or {}).items()},
            tags=unique_preserving_order([str(tag).strip() for tag in (tags or []) if str(tag).strip()]),
        )
        self._save_inventory()
        return self.devices[key].to_dict()

    def update_device(
        self,
        device_id: str,
        *,
        display_name: str | None = None,
        platform: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        device = self.devices.get(device_id)
        if device is None:
            raise LookupError(f"Unknown device: {device_id}")
        if display_name is not None:
            if not display_name.strip():
                raise ValueError("display_name cannot be empty.")
            device.display_name = display_name.strip()
        if platform is not None:
            device.platform = platform.strip()
        if metadata is not None:
            device.metadata = {str(name): str(value) for name, value in metadata.items()}
        if tags is not None:
            device.tags = unique_preserving_order([str(tag).strip() for tag in tags if str(tag).strip()])
        self._save_inventory()
        return device.to_dict()

    def delete_device(self, device_id: str) -> dict[str, Any]:
        if device_id not in self.devices:
            raise LookupError(f"Unknown device: {device_id}")
        del self.devices[device_id]
        removed_installations = len([item for item in self.installations if item.device_id == device_id])
        self.installations = [item for item in self.installations if item.device_id != device_id]
        self._save_inventory()
        return {"device_id": device_id, "removed_installations": removed_installations}

    def list_installations(
        self,
        *,
        account_id: str | None = None,
        device_id: str | None = None,
        agent_name: str | None = None,
        skill: str | None = None,
    ) -> list[dict[str, Any]]:
        items = self._filtered_installations(
            account_id=account_id,
            device_id=device_id,
            agent_name=agent_name,
            skill=skill,
        )
        return [self._installation_to_dict(item) for item in items]

    def assign_agent_installation(
        self,
        *,
        account_id: str,
        device_id: str,
        agent_name: str,
        skills: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        if account_id not in self.accounts:
            raise LookupError(f"Unknown account: {account_id}")
        if device_id not in self.devices:
            raise LookupError(f"Unknown device: {device_id}")
        if not agent_name.strip():
            raise ValueError("agent_name is required.")
        normalized_agent_name = agent_name.strip()
        normalized_skills = unique_preserving_order([str(skill).strip() for skill in (skills or []) if str(skill).strip()])
        existing = self._find_installation(account_id=account_id, device_id=device_id, agent_name=normalized_agent_name)
        if existing is None:
            record = InstallationRecord(
                account_id=account_id,
                device_id=device_id,
                agent_name=normalized_agent_name,
                skills=normalized_skills,
                notes=notes.strip(),
            )
            self.installations.append(record)
            self.installations.sort(key=lambda item: (item.account_id.casefold(), item.device_id.casefold(), item.agent_name.casefold()))
            saved = record
        else:
            existing.skills = normalized_skills
            existing.notes = notes.strip()
            saved = existing
        self._save_inventory()
        return self._installation_to_dict(saved)

    def remove_agent_installation(self, *, account_id: str, device_id: str, agent_name: str) -> dict[str, Any]:
        previous_count = len(self.installations)
        self.installations = [
            item
            for item in self.installations
            if not (
                item.account_id == account_id
                and item.device_id == device_id
                and item.agent_name.casefold() == agent_name.casefold()
            )
        ]
        removed = previous_count != len(self.installations)
        if removed:
            self._save_inventory()
        return {
            "account_id": account_id,
            "device_id": device_id,
            "agent_name": agent_name,
            "removed": removed,
        }

    def where_is_agent_installed(self, agent_name: str) -> dict[str, Any]:
        if not agent_name.strip():
            raise ValueError("agent_name is required.")
        installs = self._filtered_installations(agent_name=agent_name)
        return {
            "agent_name": agent_name,
            "installations": [self._installation_to_dict(item) for item in installs],
        }

    def skills_for_account_device(self, account_id: str, device_id: str) -> dict[str, Any]:
        installs = self._filtered_installations(account_id=account_id, device_id=device_id)
        skills: list[str] = []
        for installation in installs:
            skills.extend(installation.skills)
        return {
            "account_id": account_id,
            "device_id": device_id,
            "agents": [self._installation_to_dict(item) for item in installs],
            "skills": unique_preserving_order(skills),
        }

    def search_inventory(
        self,
        *,
        account_id: str = "",
        device_id: str = "",
        agent_name: str = "",
        skill: str = "",
        path: str = "",
    ) -> dict[str, Any]:
        installations = self._filtered_installations(
            account_id=account_id or None,
            device_id=device_id or None,
            agent_name=agent_name or None,
            skill=skill or None,
        )
        files = self.list_managed_files(path_query=path)
        return {
            "filters": {
                "account_id": account_id,
                "device_id": device_id,
                "agent_name": agent_name,
                "skill": skill,
                "path": path,
            },
            "installations": [self._installation_to_dict(item) for item in installations],
            "files": files,
        }

    def inventory_coverage(self) -> dict[str, Any]:
        assigned_device_ids = {item.device_id for item in self.installations}
        assigned_account_ids = {item.account_id for item in self.installations}
        all_skills = unique_preserving_order(
            skill
            for installation in self.installations
            for skill in installation.skills
        )
        return {
            "totals": {
                "accounts": len(self.accounts),
                "devices": len(self.devices),
                "installations": len(self.installations),
                "skills": len(all_skills),
            },
            "unassigned_devices": sorted(
                [device_id for device_id in self.devices if device_id not in assigned_device_ids],
                key=str.casefold,
            ),
            "unused_accounts": sorted(
                [account_id for account_id in self.accounts if account_id not in assigned_account_ids],
                key=str.casefold,
            ),
            "skills": all_skills,
        }

    def list_managed_files(self, *, path_query: str = "") -> list[dict[str, Any]]:
        query = path_query.casefold().strip()
        records: list[dict[str, Any]] = []
        for discovered in scan_agent_files(self.config):
            file_name = Path(discovered.agent_file_path).name
            if file_name.casefold() not in _SUPPORTED_MANAGED_FILENAMES:
                continue
            managed = ManagedFileRecord(
                path=discovered.agent_file_path,
                file_name=file_name,
                sha256=discovered.sha256,
                mtime=discovered.mtime,
                file_size=discovered.file_size,
            ).to_dict()
            if query and query not in managed["path"].casefold():
                continue
            records.append(managed)
        records.sort(key=lambda item: item["path"].casefold())
        return records

    def read_managed_file(self, path: str | Path) -> dict[str, Any]:
        normalized_path = self._validate_managed_file_path(path, must_exist=True)
        stat = normalized_path.stat()
        return {
            "path": str(normalized_path),
            "file_name": normalized_path.name,
            "sha256": sha256_file(normalized_path),
            "mtime": stat.st_mtime,
            "file_size": stat.st_size,
            "content": read_text_file(normalized_path),
        }

    def update_managed_file(
        self,
        path: str | Path,
        content: str,
        *,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        normalized_path = self._validate_managed_file_path(path, must_exist=False)
        if expected_sha256 and normalized_path.exists():
            current_sha = sha256_file(normalized_path)
            if current_sha != expected_sha256:
                raise ValueError("File update conflict: expected_sha256 does not match current file.")
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(normalized_path, content)
        self.refresh_index()
        return self.read_managed_file(normalized_path)

    def update_managed_file_section(
        self,
        path: str | Path,
        section_heading: str,
        section_content: str,
        *,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        section_name = section_heading.strip()
        if not section_name:
            raise ValueError("section_heading is required.")
        current = self.read_managed_file(path)
        if expected_sha256 and current["sha256"] != expected_sha256:
            raise ValueError("File update conflict: expected_sha256 does not match current file.")
        updated_content = _upsert_markdown_section(
            current["content"],
            section_heading=section_name,
            section_content=section_content,
        )
        return self.update_managed_file(path, updated_content)

    def _load_inventory(self) -> None:
        snapshot = self.inventory_store.load()
        self.accounts = {item.account_id: item for item in snapshot.accounts}
        self.devices = {item.device_id: item for item in snapshot.devices}
        self.installations = sorted(
            snapshot.installations,
            key=lambda item: (item.account_id.casefold(), item.device_id.casefold(), item.agent_name.casefold()),
        )

    def _save_inventory(self) -> None:
        self.inventory_store.save(
            InventorySnapshot(
                accounts=[self.accounts[key] for key in sorted(self.accounts, key=str.casefold)],
                devices=[self.devices[key] for key in sorted(self.devices, key=str.casefold)],
                installations=list(self.installations),
            )
        )

    def _find_installation(self, *, account_id: str, device_id: str, agent_name: str) -> InstallationRecord | None:
        for item in self.installations:
            if (
                item.account_id == account_id
                and item.device_id == device_id
                and item.agent_name.casefold() == agent_name.casefold()
            ):
                return item
        return None

    def _filtered_installations(
        self,
        *,
        account_id: str | None = None,
        device_id: str | None = None,
        agent_name: str | None = None,
        skill: str | None = None,
    ) -> list[InstallationRecord]:
        normalized_agent = agent_name.casefold() if agent_name else None
        normalized_skill = skill.casefold() if skill else None
        return [
            item
            for item in self.installations
            if (account_id is None or item.account_id == account_id)
            and (device_id is None or item.device_id == device_id)
            and (normalized_agent is None or item.agent_name.casefold() == normalized_agent)
            and (
                normalized_skill is None
                or any(candidate.casefold() == normalized_skill for candidate in item.skills)
            )
        ]

    def _installation_to_dict(self, item: InstallationRecord) -> dict[str, Any]:
        account = self.accounts.get(item.account_id)
        device = self.devices.get(item.device_id)
        payload = item.to_dict()
        payload["account"] = account.to_dict() if account else {"account_id": item.account_id}
        payload["device"] = device.to_dict() if device else {"device_id": item.device_id}
        return payload

    def _validate_managed_file_path(self, path: str | Path, *, must_exist: bool) -> Path:
        normalized_path = normalize_path(path, follow_symlinks=self.config.follow_symlinks)
        if not ensure_within_roots(normalized_path, self.config.roots):
            raise ValueError(f"Path is outside configured roots: {normalized_path}")
        if normalized_path.name.casefold() not in _SUPPORTED_MANAGED_FILENAMES:
            raise ValueError(
                f"Unsupported managed file: {normalized_path.name}. "
                "Only AGENTS.md and CLAUDE.md variants are supported."
            )
        if must_exist and not normalized_path.exists():
            raise FileNotFoundError(f"Managed file not found: {normalized_path}")
        if normalized_path.exists() and normalized_path.is_dir():
            raise ValueError(f"Managed file path points to a directory: {normalized_path}")
        return normalized_path


def _build_previous_signatures(
    current_projects: list[ProjectRecord],
    cached_entries: dict[str, CacheEntry],
) -> dict[str, tuple[str, int, float]]:
    if current_projects:
        return {
            project.agent_file_path: (project.sha256, project.file_size, project.mtime)
            for project in current_projects
        }
    return {
        entry.agent_file_path: (entry.sha256, entry.file_size, entry.mtime)
        for entry in cached_entries.values()
    }


def _assign_project_names(records: list[ProjectRecord]) -> list[ProjectRecord]:
    display_candidates: dict[str, list[ProjectRecord]] = {}
    for record in records:
        display_candidates.setdefault(_base_project_name(record), []).append(record)

    named_records: list[ProjectRecord] = []
    for base_name, group in display_candidates.items():
        if len(group) == 1:
            named_records.append(replace(group[0], project_name=base_name))
            continue
        for record in group:
            suffix = record.relative_root_from_scan_base
            if suffix == ".":
                suffix = Path(record.scan_root).name
            named_records.append(replace(record, project_name=f"{base_name} [{suffix}]"))
    return named_records


def _base_project_name(record: ProjectRecord) -> str:
    project_root = Path(record.project_root)
    return project_root.name or Path(record.scan_root).name


def _assign_relationships(records: list[ProjectRecord]) -> None:
    by_root = {Path(record.project_root): record for record in records}
    for record in records:
        record.child_project_names.clear()

    for record in records:
        project_root = Path(record.project_root)
        parent_record: ProjectRecord | None = None
        for parent_root, candidate in by_root.items():
            if parent_root == project_root:
                continue
            try:
                project_root.relative_to(parent_root)
            except ValueError:
                continue
            if parent_record is None or len(parent_root.parts) > len(Path(parent_record.project_root).parts):
                parent_record = candidate
        record.parent_project_name = parent_record.project_name if parent_record else None

    by_name = {record.project_name: record for record in records}
    for record in records:
        if record.parent_project_name:
            by_name[record.parent_project_name].child_project_names.append(record.project_name)
    for record in records:
        record.child_project_names.sort(key=str.casefold)


def _score_project(project: ProjectRecord, terms: list[str]) -> int:
    fields = [
        (project.project_name.casefold(), 12),
        (project.project_root.casefold(), 8),
        (project.agent_file_path.casefold(), 8),
        (" ".join(tag.casefold() for tag in project.tags), 6),
        (project.summary.casefold(), 5),
        (project.raw_markdown.casefold(), 2),
    ]
    score = 0
    for term in terms:
        term_score = sum(weight for value, weight in fields if term in value)
        if term_score == 0:
            return 0
        score += term_score
    return score


_SUPPORTED_MANAGED_FILENAMES = {
    "agents.md",
    "claude.md",
}


def _atomic_write_text(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(path)


def _upsert_markdown_section(raw_markdown: str, *, section_heading: str, section_content: str) -> str:
    lines = raw_markdown.splitlines()
    target = section_heading.strip().casefold()
    start_index: int | None = None
    end_index: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading_text = stripped.lstrip("#").strip()
        if start_index is None:
            if heading_text.casefold() == target:
                start_index = index
            continue
        if stripped.startswith("#"):
            end_index = index
            break

    block = [f"## {section_heading.strip()}"]
    section_lines = section_content.splitlines() if section_content else []
    block.extend(section_lines)

    if start_index is None:
        if lines and lines[-1].strip():
            lines.extend(["", *block])
        else:
            lines.extend(block)
    else:
        replace_end = end_index if end_index is not None else len(lines)
        lines[start_index:replace_end] = block
    output = "\n".join(lines).strip() + "\n"
    return output
