"""Local-only REST API for the project registry.

No endpoint runs agents or reads/writes files in registered repositories.
"""

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from multi_agent_software_team.projects import Project, ProjectManager


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    kind: Literal["managed", "existing"]
    description: str
    created_at: str
    read_only: bool


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)


class RegisterProjectRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None
    description: str = Field(default="", max_length=2000)


def _response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        path=str(project.path),
        kind=project.kind.value,
        description=project.description,
        created_at=project.created_at,
        read_only=project.read_only,
    )


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    """Create an independently testable API instance with its own registry."""
    if data_dir is None:
        data_dir = os.environ.get("STUDIO_DATA_DIR", ".studio-data")
    manager = ProjectManager(data_dir)
    app = FastAPI(title="Multi-Agent Studio API", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/projects", response_model=list[ProjectResponse])
    def list_projects() -> list[ProjectResponse]:
        return [_response(project) for project in manager.list_projects()]

    @app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
    def create_project(request: CreateProjectRequest) -> ProjectResponse:
        try:
            return _response(manager.create(request.name, request.description))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/projects/register", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
    def register_project(request: RegisterProjectRequest) -> ProjectResponse:
        try:
            return _response(manager.register_existing(request.path, request.name, request.description))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}", response_model=ProjectResponse)
    def get_project(project_id: str) -> ProjectResponse:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _response(project)

    return app


app = create_app()
