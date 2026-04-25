from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .registry import AgentsRegistry


def create_web_app(config_path: str | None = None) -> Any:
    FastAPI, HTMLResponse, HTTPException, StaticFiles = _load_fastapi_components()

    resolved_config_path = config_path or os.environ.get("AGENTS_REGISTRY_CONFIG", "config.yaml")
    registry = AgentsRegistry.from_config_path(resolved_config_path)
    registry.refresh_index()

    app = FastAPI(title="Agents Registry Admin", version="0.1.0")
    static_dir = _assets_dir() / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def admin_ui() -> str:
        return _load_admin_template()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/projects")
    def list_projects() -> dict[str, object]:
        return {"projects": registry.list_projects()}

    @app.get("/api/projects/{project_name}")
    def get_project(project_name: str) -> dict[str, object]:
        try:
            return registry.get_project(project_name)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_name}/effective")
    def get_project_effective(project_name: str) -> dict[str, object]:
        try:
            return registry.resolve_project_root(project_name)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/search")
    def search_projects(query: str = "") -> dict[str, object]:
        return registry.search_projects(query)

    @app.get("/api/context")
    def resolve_context(path: str) -> dict[str, object]:
        try:
            return registry.resolve_context(path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/refresh")
    def refresh_index() -> dict[str, int]:
        return registry.refresh_index().to_dict()

    @app.get("/api/accounts")
    def list_accounts() -> dict[str, object]:
        return {"accounts": registry.list_accounts()}

    @app.post("/api/accounts")
    def create_account(payload: dict[str, object]) -> dict[str, object]:
        try:
            return registry.create_account(
                account_id=str(payload.get("account_id", "")),
                display_name=str(payload.get("display_name", "")),
                provider=str(payload.get("provider", "")),
                metadata=dict(payload.get("metadata", {})) if isinstance(payload.get("metadata", {}), dict) else {},
                tags=[str(tag) for tag in list(payload.get("tags", []))],
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/accounts/{account_id}")
    def update_account(account_id: str, payload: dict[str, object]) -> dict[str, object]:
        try:
            tags = payload.get("tags", None)
            metadata = payload.get("metadata", None)
            return registry.update_account(
                account_id=account_id,
                display_name=str(payload["display_name"]) if "display_name" in payload else None,
                provider=str(payload["provider"]) if "provider" in payload else None,
                metadata=dict(metadata) if isinstance(metadata, dict) else None,
                tags=[str(tag) for tag in tags] if isinstance(tags, list) else None,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/accounts/{account_id}")
    def delete_account(account_id: str) -> dict[str, object]:
        try:
            return registry.delete_account(account_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/devices")
    def list_devices() -> dict[str, object]:
        return {"devices": registry.list_devices()}

    @app.post("/api/devices")
    def create_device(payload: dict[str, object]) -> dict[str, object]:
        try:
            return registry.create_device(
                device_id=str(payload.get("device_id", "")),
                display_name=str(payload.get("display_name", "")),
                platform=str(payload.get("platform", "")),
                metadata=dict(payload.get("metadata", {})) if isinstance(payload.get("metadata", {}), dict) else {},
                tags=[str(tag) for tag in list(payload.get("tags", []))],
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/devices/{device_id}")
    def update_device(device_id: str, payload: dict[str, object]) -> dict[str, object]:
        try:
            tags = payload.get("tags", None)
            metadata = payload.get("metadata", None)
            return registry.update_device(
                device_id=device_id,
                display_name=str(payload["display_name"]) if "display_name" in payload else None,
                platform=str(payload["platform"]) if "platform" in payload else None,
                metadata=dict(metadata) if isinstance(metadata, dict) else None,
                tags=[str(tag) for tag in tags] if isinstance(tags, list) else None,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/devices/{device_id}")
    def delete_device(device_id: str) -> dict[str, object]:
        try:
            return registry.delete_device(device_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/installations")
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

    @app.post("/api/installations")
    def assign_installation(payload: dict[str, object]) -> dict[str, object]:
        try:
            skills = payload.get("skills", [])
            return registry.assign_agent_installation(
                account_id=str(payload.get("account_id", "")),
                device_id=str(payload.get("device_id", "")),
                agent_name=str(payload.get("agent_name", "")),
                skills=[str(item) for item in skills] if isinstance(skills, list) else [],
                notes=str(payload.get("notes", "")),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/installations")
    def remove_installation(account_id: str, device_id: str, agent_name: str) -> dict[str, object]:
        return registry.remove_agent_installation(
            account_id=account_id,
            device_id=device_id,
            agent_name=agent_name,
        )

    @app.get("/api/inventory/coverage")
    def inventory_coverage() -> dict[str, object]:
        return registry.inventory_coverage()

    @app.get("/api/inventory/search")
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

    @app.get("/api/inventory/where-agent")
    def where_agent_installed(agent_name: str) -> dict[str, object]:
        try:
            return registry.where_is_agent_installed(agent_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/inventory/skills")
    def skills_for_account_device(account_id: str, device_id: str) -> dict[str, object]:
        return registry.skills_for_account_device(account_id, device_id)

    @app.get("/api/files")
    def list_managed_files(path_query: str = "") -> dict[str, object]:
        return {"files": registry.list_managed_files(path_query=path_query)}

    @app.get("/api/files/read")
    def read_managed_file(path: str) -> dict[str, object]:
        try:
            return registry.read_managed_file(path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/files/write")
    def write_managed_file(payload: dict[str, object]) -> dict[str, object]:
        try:
            return registry.update_managed_file(
                path=str(payload.get("path", "")),
                content=str(payload.get("content", "")),
                expected_sha256=str(payload.get("expected_sha256", "")).strip() or None,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/files/write-section")
    def write_managed_file_section(payload: dict[str, object]) -> dict[str, object]:
        try:
            return registry.update_managed_file_section(
                path=str(payload.get("path", "")),
                section_heading=str(payload.get("section_heading", "")),
                section_content=str(payload.get("section_content", "")),
                expected_sha256=str(payload.get("expected_sha256", "")).strip() or None,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def _load_fastapi_components() -> tuple[type[Any], type[Any], type[Any], type[Any]]:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI dependencies are missing. Install with: pip install -e .[web]"
        ) from exc
    return FastAPI, HTMLResponse, HTTPException, StaticFiles


def _load_uvicorn() -> Any:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "Uvicorn is missing. Install with: pip install -e .[web]"
        ) from exc
    return uvicorn


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent / "web_assets"


def _load_admin_template() -> str:
    template_path = _assets_dir() / "templates" / "admin.html"
    if not template_path.exists():
        raise RuntimeError(f"Missing admin template file: {template_path}")
    return template_path.read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agents Registry admin web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8002, help="Port to bind (default: 8002)")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (defaults to AGENTS_REGISTRY_CONFIG or ./config.yaml)",
    )
    args = parser.parse_args()

    uvicorn = _load_uvicorn()
    app = create_web_app(args.config)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
