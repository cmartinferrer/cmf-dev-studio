"""Local-only REST API for the project registry.

No endpoint runs agents or reads/writes files in registered repositories.
"""

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, status, WebSocket
from multi_agent_software_team.api.terminal import terminal_socket
from pydantic import BaseModel, Field

from multi_agent_software_team.projects import Project, ProjectManager
from multi_agent_software_team.projects.explorer import ExplorerError, list_directory, read_file
from multi_agent_software_team.missions import MissionService
from multi_agent_software_team.workspaces import WorkspaceService, WorkspaceError
from multi_agent_software_team.projects.browser import FolderBrowserError, browse_directory
from multi_agent_software_team.projects.search import search_files
from multi_agent_software_team.projects.editor import read_editable, write_editable, delete_editable, EditConflict
from multi_agent_software_team.projects.intelligence import analyze_repository, prepare_context


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
    missions = MissionService(manager)
    workspaces = WorkspaceService(manager)
    missions.recover_interrupted()
    app = FastAPI(title="Multi-Agent Studio API", version="0.1.0")

    @app.websocket("/api/projects/{project_id}/terminal")
    async def project_terminal(websocket: WebSocket, project_id: str) -> None:
        await terminal_socket(websocket, manager)

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

    @app.get("/api/local/directories")
    def local_directories(path: str = "") -> dict:
        try:
            return browse_directory(path)
        except (FolderBrowserError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/search")
    def project_search(project_id: str, q: str) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return search_files(project.path, q)
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/files")
    def project_files(project_id: str, path: str = "") -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return list_directory(project.path, path)
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/file")
    def project_file(project_id: str, path: str) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return read_file(project.path, path)
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    class EditRequest(BaseModel):
        path: str = Field(min_length=1, max_length=500)
        content: str = Field(max_length=262144)
        expected_sha256: str | None = None
        create: bool = False
        authorize_existing: bool = False

    class DeleteRequest(BaseModel):
        path: str = Field(min_length=1, max_length=500)
        expected_sha256: str
        authorize_existing: bool = False

    def editable_project(project_id: str, authorize_existing: bool):
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.read_only and not authorize_existing:
            raise HTTPException(status_code=403, detail="Explicit authorization required for existing projects")
        return project

    @app.get("/api/projects/{project_id}/editor/file")
    def editor_file(project_id: str, path: str) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return read_editable(project.path, path)
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/projects/{project_id}/editor/file")
    def editor_save(project_id: str, request: EditRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        try:
            return write_editable(project.path, request.path, request.content, request.expected_sha256, create=request.create)
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/projects/{project_id}/editor/file")
    def editor_delete(project_id: str, request: DeleteRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        try:
            return delete_editable(project.path, request.path, request.expected_sha256)
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/insights")
    def project_insights(project_id: str) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return analyze_repository(project.path)

    class ContextRequest(BaseModel):
        paths: list[str] = Field(default_factory=list, max_length=8)

    @app.post("/api/projects/{project_id}/context/preview")
    def context_preview(project_id: str, request: ContextRequest) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return prepare_context(project.path, request.paths)
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    class MissionRequest(BaseModel):
        description: str = Field(min_length=1, max_length=10000)
        context_paths: list[str] = Field(default_factory=list, max_length=8)
        context_digest: str | None = None

    @app.post("/api/projects/{project_id}/missions", status_code=status.HTTP_202_ACCEPTED)
    def start_mission(project_id: str, request: MissionRequest) -> dict:
        try:
            return missions.submit(project_id, request.description, request.context_paths, request.context_digest)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, ExplorerError, OSError) as exc:
            code = 409 if "already active" in str(exc) else 422
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/missions")
    def list_missions(project_id: str) -> list[dict]:
        if manager.get(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return missions.list_for_project(project_id)

    @app.get("/api/missions/{run_id}")
    def get_mission(run_id: str) -> dict:
        run = missions.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        return run

    @app.get("/api/missions/{run_id}/events")
    def get_mission_events(run_id: str, after_id: int = 0) -> list[dict]:
        if missions.get(run_id) is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        if after_id < 0:
            raise HTTPException(status_code=422, detail="after_id must be non-negative")
        return missions.events(run_id, after_id)

    class ProposalRequest(BaseModel):
        task: str = Field(min_length=1, max_length=4000)
        context_paths: list[str] = Field(default_factory=list, max_length=8)
        context_digest: str | None = None

    @app.post("/api/projects/{project_id}/proposals", status_code=status.HTTP_202_ACCEPTED)
    def create_proposal(project_id: str, request: ProposalRequest) -> dict:
        try:
            return workspaces.submit(project_id, request.task, request.context_paths, request.context_digest)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/proposals")
    def list_proposals(project_id: str) -> list[dict]:
        if manager.get(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return workspaces.list(project_id)

    @app.get("/api/proposals/{proposal_id}")
    def get_proposal(proposal_id: str) -> dict:
        try:
            return workspaces.get(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/proposals/{proposal_id}/preview")
    def preview_proposal_file(proposal_id: str, path: str) -> dict:
        try:
            return workspaces.preview_file(proposal_id, path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError, UnicodeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    class ApplyRequest(BaseModel):
        confirmation: str
        allow_existing: bool = False

    @app.post("/api/proposals/{proposal_id}/test")
    def test_proposal(proposal_id: str) -> dict:
        try:
            return workspaces.test(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/proposals/{proposal_id}/apply")
    def apply_proposal(proposal_id: str, request: ApplyRequest) -> dict:
        try:
            return workspaces.apply(proposal_id, request.confirmation, request.allow_existing)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
