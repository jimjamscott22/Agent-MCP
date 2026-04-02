from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import normalize_path

DEFAULT_AGENT_FILENAMES = ("AGENTS.md", "agents.md", "CLAUDE.md", "claude.md")
DEFAULT_IGNORE_DIRS = (".git", "node_modules", ".venv", "dist", "build", "__pycache__")


@dataclass(slots=True)
class AppConfig:
    roots: tuple[Path, ...]
    agent_filenames: tuple[str, ...] = DEFAULT_AGENT_FILENAMES
    ignore_dirs: tuple[str, ...] = DEFAULT_IGNORE_DIRS
    merge_mode: str = "hierarchy"
    cache_enabled: bool = True
    parse_sections: bool = True
    follow_symlinks: bool = False
    cache_path: Path | None = None
    inventory_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.roots:
            raise ValueError("At least one root directory must be configured.")
        if self.merge_mode != "hierarchy":
            raise ValueError("Only merge_mode='hierarchy' is currently supported.")
        invalid_names = [name for name in self.agent_filenames if not name or "/" in name or "\\" in name]
        if invalid_names:
            raise ValueError(f"Invalid agent file names: {invalid_names}")
        normalized_roots: list[Path] = []
        for root in self.roots:
            normalized = normalize_path(root, follow_symlinks=self.follow_symlinks)
            if not normalized.exists():
                raise ValueError(f"Configured root does not exist: {normalized}")
            if not normalized.is_dir():
                raise ValueError(f"Configured root is not a directory: {normalized}")
            normalized_roots.append(normalized)
        self.roots = tuple(normalized_roots)
        self.agent_filenames = tuple(dict.fromkeys(self.agent_filenames))
        self.ignore_dirs = tuple(dict.fromkeys(self.ignore_dirs))
        if self.cache_path is not None:
            self.cache_path = normalize_path(self.cache_path, follow_symlinks=self.follow_symlinks)
        if self.inventory_path is not None:
            self.inventory_path = normalize_path(self.inventory_path, follow_symlinks=self.follow_symlinks)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], *, config_path: Path | None = None) -> "AppConfig":
        raw_roots = payload.get("roots")
        if not isinstance(raw_roots, list) or not raw_roots:
            raise ValueError("Config field 'roots' must be a non-empty list.")
        base_dir = config_path.parent if config_path is not None else Path.cwd()
        roots = tuple(_resolve_declared_path(base_dir, value) for value in raw_roots)
        cache_path_value = payload.get("cache_path")
        cache_path = _resolve_declared_path(base_dir, cache_path_value) if cache_path_value else base_dir / ".cache" / "agents_registry_cache.json"
        inventory_path_value = payload.get("inventory_path")
        inventory_path = (
            _resolve_declared_path(base_dir, inventory_path_value)
            if inventory_path_value
            else base_dir / ".cache" / "agents_inventory.json"
        )
        return cls(
            roots=roots,
            agent_filenames=tuple(payload.get("agent_filenames", DEFAULT_AGENT_FILENAMES)),
            ignore_dirs=tuple(payload.get("ignore_dirs", DEFAULT_IGNORE_DIRS)),
            merge_mode=str(payload.get("merge_mode", "hierarchy")),
            cache_enabled=bool(payload.get("cache_enabled", True)),
            parse_sections=bool(payload.get("parse_sections", True)),
            follow_symlinks=bool(payload.get("follow_symlinks", False)),
            cache_path=cache_path,
            inventory_path=inventory_path,
        )


def _resolve_declared_path(base_dir: Path, raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else base_dir / path


def load_config(config_path: str | Path) -> AppConfig:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load config files. Install dependencies first.") from exc

    normalized_path = Path(config_path).expanduser()
    if not normalized_path.exists():
        raise FileNotFoundError(f"Config file not found: {normalized_path}")
    payload = yaml.safe_load(normalized_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Config file must contain a top-level mapping.")
    return AppConfig.from_mapping(payload, config_path=normalized_path)
