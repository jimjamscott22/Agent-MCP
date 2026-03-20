from __future__ import annotations

import os
from pathlib import Path

from .config import AppConfig
from .models import DiscoveredAgentFile
from .utils import normalize_path, sha256_file


def scan_agent_files(config: AppConfig) -> list[DiscoveredAgentFile]:
    discovered: list[DiscoveredAgentFile] = []
    allowed_names = set(config.agent_filenames)
    ignored = set(config.ignore_dirs)

    for root in config.roots:
        for current_root, dirnames, filenames in os.walk(root, followlinks=config.follow_symlinks):
            current_path = Path(current_root)
            dirnames[:] = _filter_dirnames(
                dirnames,
                current_path=current_path,
                ignored=ignored,
                follow_symlinks=config.follow_symlinks,
            )
            for filename in filenames:
                if filename not in allowed_names:
                    continue
                agent_path = current_path / filename
                if not config.follow_symlinks and agent_path.is_symlink():
                    continue
                try:
                    stat = agent_path.stat()
                    sha256 = sha256_file(agent_path)
                except OSError:
                    continue
                project_root = normalize_path(agent_path.parent, follow_symlinks=config.follow_symlinks)
                relative_root = os.path.relpath(project_root, root)
                relative_root = "." if relative_root == "." else relative_root.replace(os.sep, "/")
                depth = 0 if relative_root == "." else len(Path(relative_root).parts)
                discovered.append(
                    DiscoveredAgentFile(
                        scan_root=str(root),
                        agent_file_path=str(agent_path),
                        project_root=str(project_root),
                        relative_root_from_scan_base=relative_root,
                        depth=depth,
                        file_size=stat.st_size,
                        mtime=stat.st_mtime,
                        sha256=sha256,
                    )
                )
    discovered.sort(key=lambda item: (item.scan_root, item.project_root, item.agent_file_path))
    return discovered


def _filter_dirnames(
    dirnames: list[str],
    *,
    current_path: Path,
    ignored: set[str],
    follow_symlinks: bool,
) -> list[str]:
    filtered: list[str] = []
    for dirname in dirnames:
        if dirname in ignored:
            continue
        child = current_path / dirname
        if not follow_symlinks and child.is_symlink():
            continue
        filtered.append(dirname)
    return filtered
