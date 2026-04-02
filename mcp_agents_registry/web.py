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
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
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