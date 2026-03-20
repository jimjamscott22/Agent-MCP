from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, TypeVar
from urllib.parse import quote, unquote

T = TypeVar("T")


def normalize_path(path: str | Path, *, follow_symlinks: bool) -> Path:
    expanded = Path(path).expanduser()
    normalized = os.path.realpath(str(expanded)) if follow_symlinks else os.path.abspath(str(expanded))
    return Path(normalized)


def is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_within_roots(path: Path, roots: Iterable[Path]) -> bool:
    return any(is_within_root(path, root) for root in roots)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def isoformat_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()


def unique_preserving_order(values: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    ordered: list[T] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def compact_text(value: str, *, limit: int = 240) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3].rstrip()}..."


def encode_resource_path(path: str | Path) -> str:
    return quote(str(path), safe="")


def decode_resource_path(value: str) -> str:
    return unquote(value)


def to_pretty_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)
