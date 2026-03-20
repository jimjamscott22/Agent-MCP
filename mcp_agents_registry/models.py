from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import isoformat_timestamp


@dataclass(slots=True)
class ParsedAgentContent:
    sections: dict[str, str] = field(default_factory=dict)
    other_sections: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": dict(self.sections),
            "other_sections": dict(self.other_sections),
            "summary": self.summary,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ParsedAgentContent":
        return cls(
            sections=dict(payload.get("sections", {})),
            other_sections=dict(payload.get("other_sections", {})),
            summary=str(payload.get("summary", "")),
            tags=list(payload.get("tags", [])),
        )


@dataclass(slots=True)
class DiscoveredAgentFile:
    scan_root: str
    agent_file_path: str
    project_root: str
    relative_root_from_scan_base: str
    depth: int
    file_size: int
    mtime: float
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_root": self.scan_root,
            "agent_file_path": self.agent_file_path,
            "project_root": self.project_root,
            "relative_root_from_scan_base": self.relative_root_from_scan_base,
            "depth": self.depth,
            "file_size": self.file_size,
            "mtime": self.mtime,
            "sha256": self.sha256,
        }


@dataclass(slots=True)
class ProjectRecord:
    project_name: str
    agent_file_path: str
    project_root: str
    scan_root: str
    relative_root_from_scan_base: str
    parent_project_name: str | None
    depth: int
    raw_markdown: str
    parsed_sections: ParsedAgentContent
    tags: list[str]
    summary: str
    mtime: float
    sha256: str
    file_size: int
    child_project_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "agent_file_path": self.agent_file_path,
            "project_root": self.project_root,
            "scan_root": self.scan_root,
            "relative_root_from_scan_base": self.relative_root_from_scan_base,
            "parent_project_name": self.parent_project_name,
            "child_project_names": list(self.child_project_names),
            "depth": self.depth,
            "raw_markdown": self.raw_markdown,
            "parsed_sections": self.parsed_sections.to_dict(),
            "tags": list(self.tags),
            "summary": self.summary,
            "mtime": self.mtime,
            "last_modified": isoformat_timestamp(self.mtime),
            "sha256": self.sha256,
            "file_size": self.file_size,
        }


@dataclass(slots=True)
class CacheEntry:
    agent_file_path: str
    mtime: float
    sha256: str
    file_size: int
    raw_markdown: str
    parsed_content: ParsedAgentContent

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_file_path": self.agent_file_path,
            "mtime": self.mtime,
            "sha256": self.sha256,
            "file_size": self.file_size,
            "raw_markdown": self.raw_markdown,
            "parsed_content": self.parsed_content.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CacheEntry":
        return cls(
            agent_file_path=str(payload["agent_file_path"]),
            mtime=float(payload["mtime"]),
            sha256=str(payload["sha256"]),
            file_size=int(payload["file_size"]),
            raw_markdown=str(payload.get("raw_markdown", "")),
            parsed_content=ParsedAgentContent.from_dict(payload.get("parsed_content", {})),
        )


@dataclass(slots=True)
class ResolutionStep:
    project_name: str
    agent_file_path: str
    project_root: str
    action: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project_name": self.project_name,
            "agent_file_path": self.agent_file_path,
            "project_root": self.project_root,
            "action": self.action,
            "detail": self.detail,
        }


@dataclass(slots=True)
class EffectiveContext:
    target_path: str
    matched_projects: list[ProjectRecord]
    merged_sections: dict[str, Any]
    raw_combined_markdown: str
    resolution_trace: list[ResolutionStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_path": self.target_path,
            "matched_projects": [project.to_dict() for project in self.matched_projects],
            "matched_agent_files": [project.agent_file_path for project in self.matched_projects],
            "merged_sections": self.merged_sections,
            "raw_combined_markdown": self.raw_combined_markdown,
            "resolution_trace": [step.to_dict() for step in self.resolution_trace],
        }


@dataclass(slots=True)
class RefreshSummary:
    project_count: int
    added: int
    changed: int
    removed: int

    def to_dict(self) -> dict[str, int]:
        return {
            "project_count": self.project_count,
            "added": self.added,
            "changed": self.changed,
            "removed": self.removed,
        }
