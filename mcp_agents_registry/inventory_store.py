from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import AccountRecord, DeviceRecord, InstallationRecord, InventorySnapshot

INVENTORY_VERSION = 1


class InventoryStore:
    def __init__(self, inventory_path: Path | None) -> None:
        self.inventory_path = inventory_path

    def load(self) -> InventorySnapshot:
        if self.inventory_path is None or not self.inventory_path.exists():
            return InventorySnapshot()
        payload = json.loads(self.inventory_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Inventory file must contain a top-level mapping.")
        raw_version = payload.get("version", 0)
        try:
            version = int(raw_version)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid inventory version format: {raw_version!r}. Expected integer {INVENTORY_VERSION}."
            ) from exc
        if version != INVENTORY_VERSION:
            raise ValueError(f"Unsupported inventory version: {version}")
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Inventory payload field 'data' must be a mapping.")
        snapshot = InventorySnapshot.from_dict(data)
        _validate_snapshot(snapshot)
        return snapshot

    def save(self, snapshot: InventorySnapshot) -> None:
        if self.inventory_path is None:
            return
        _validate_snapshot(snapshot)
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INVENTORY_VERSION,
            "data": snapshot.to_dict(),
        }
        _atomic_write_json(self.inventory_path, payload)


def _atomic_write_json(path: Path, payload: object) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(path)


def _validate_snapshot(snapshot: InventorySnapshot) -> None:
    account_ids: set[str] = set()
    device_ids: set[str] = set()
    installation_keys: set[tuple[str, str, str]] = set()

    for account in snapshot.accounts:
        _validate_required_identifier(account.account_id, "account_id")
        if account.account_id in account_ids:
            raise ValueError(f"Duplicate account_id: {account.account_id}")
        account_ids.add(account.account_id)

    for device in snapshot.devices:
        _validate_required_identifier(device.device_id, "device_id")
        if device.device_id in device_ids:
            raise ValueError(f"Duplicate device_id: {device.device_id}")
        device_ids.add(device.device_id)

    for installation in snapshot.installations:
        _validate_required_identifier(installation.account_id, "installation.account_id")
        _validate_required_identifier(installation.device_id, "installation.device_id")
        _validate_required_identifier(installation.agent_name, "installation.agent_name")
        if installation.account_id not in account_ids:
            raise ValueError(f"Unknown account_id in installation: {installation.account_id}")
        if installation.device_id not in device_ids:
            raise ValueError(f"Unknown device_id in installation: {installation.device_id}")
        key = (installation.account_id, installation.device_id, installation.agent_name.casefold())
        if key in installation_keys:
            raise ValueError(
                "Duplicate installation for account/device/agent: "
                f"{installation.account_id}/{installation.device_id}/{installation.agent_name}"
            )
        installation_keys.add(key)


def _validate_required_identifier(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required.")
