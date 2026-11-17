"""Local REST API for projects, editor operations and AI proposals."""

import os
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, status
from pydantic import BaseModel, Field, StrictBool

from cmf_dev_studio.api.terminal import terminal_socket
from cmf_dev_studio.projects import Project, ProjectLanguage, ProjectManager
from cmf_dev_studio.projects.browser import FolderBrowserError, browse_directory
from cmf_dev_studio.projects.editor import (
    EditConflict,
    batch_entries,
    copy_entries,
    create_directory,
    delete_editable,
    delete_entry,
    directory_path,
    entry_path,
    move_entry,
    read_editable,
    rename_entry,
    safe_path,
    write_editable,
)
from cmf_dev_studio.projects.explorer import ExplorerError, list_directory, read_file
from cmf_dev_studio.projects.intelligence import analyze_repository, prepare_context
from cmf_dev_studio.projects.python_environment import (
    create_environment,
    environment_info,
    select_interpreter,
)
from cmf_dev_studio.projects.search import search_files
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    kind: Literal["managed", "existing"]
    description: str
    created_at: str
    read_only: bool
    language: ProjectLanguage


class CreateProjectRequest(BaseModel):
    language: ProjectLanguage = ProjectLanguage.AUTO
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)


class UpdateProjectLanguageRequest(BaseModel):
    language: ProjectLanguage


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
        language=project.language,
    )


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    """Create an independently testable API instance with its own registry."""
    if data_dir is None:
        data_dir = os.environ.get("STUDIO_DATA_DIR", ".studio-data")
    manager = ProjectManager(data_dir)
    workspaces = WorkspaceService(manager)
    app = FastAPI(title="CMF Dev Studio API", version=version("cmf-dev-studio"))

    @app.websocket("/api/projects/{project_id}/terminal")
    async def project_terminal(websocket: WebSocket, project_id: str) -> None:
        await terminal_socket(websocket, manager)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/projects", response_model=list[ProjectResponse])
    def list_projects() -> list[ProjectResponse]:
        return [_response(project) for project in manager.list_projects()]

    @app.post(
        "/api/projects",
        response_model=ProjectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(request: CreateProjectRequest) -> ProjectResponse:
        try:
            return _response(
                manager.create(
                    request.name, request.description, language=request.language
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post(
        "/api/projects/register",
        response_model=ProjectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def register_project(request: RegisterProjectRequest) -> ProjectResponse:
        try:
            return _response(
                manager.register_existing(
                    request.path, request.name, request.description
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}", response_model=ProjectResponse)
    def get_project(project_id: str) -> ProjectResponse:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _response(project)

    @app.patch("/api/projects/{project_id}/language", response_model=ProjectResponse)
    def update_project_language(
        project_id: str, request: UpdateProjectLanguageRequest
    ) -> ProjectResponse:
        project = manager.update_language(project_id, request.language)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _response(project)

    class PythonEnvironmentRequest(BaseModel):
        action: Literal["create", "select", "reset"]
        path: str | None = None
        confirmed: StrictBool = False

    @app.get("/api/projects/{project_id}/python-environment")
    def get_python_environment(project_id: str) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return environment_info(project)

    @app.post("/api/projects/{project_id}/python-environment")
    def update_python_environment(
        project_id: str, request: PythonEnvironmentRequest
    ) -> dict:
        project = manager.get(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if not environment_info(project)["supported"]:
            raise HTTPException(
                status_code=422,
                detail="Not a Python project; select Python as project language first",
            )
        if not request.confirmed:
            raise HTTPException(
                status_code=400, detail="Explicit confirmation required"
            )
        try:
            if request.action == "create":
                create_environment(project)
                project = manager.update_python_interpreter(project_id, None, None)
            elif request.action == "select":
                path, python_version = select_interpreter(request.path or "")
                project = manager.update_python_interpreter(
                    project_id, path, python_version
                )
            else:
                project = manager.update_python_interpreter(project_id, None, None)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return environment_info(project)

    class RenameProjectRequest(BaseModel):
        name: str = Field(min_length=1, max_length=80)

    @app.patch("/api/projects/{project_id}/name", response_model=ProjectResponse)
    def rename_project(
        project_id: str, request: RenameProjectRequest
    ) -> ProjectResponse:
        try:
            project = manager.rename(project_id, request.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _response(project)

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str, confirmed: bool = False) -> dict:
        if not confirmed:
            raise HTTPException(status_code=400, detail="Confirmation required")
        if any(
            p["status"] in ("queued", "running", "generating", "repairing")
            for p in workspaces.list(project_id)
        ):
            raise HTTPException(
                status_code=409, detail="Wait for the active AI operation"
            )
        try:
            deleted = manager.delete(project_id)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"deleted": True}

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
            raise HTTPException(
                status_code=403,
                detail="Explicit authorization required for existing projects",
            )
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
            return write_editable(
                project.path,
                request.path,
                request.content,
                request.expected_sha256,
                create=request.create,
            )
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

    class EntryRequest(BaseModel):
        path: str = Field(min_length=1, max_length=500)
        name: str | None = None
        authorize_existing: StrictBool = False
        confirmed: StrictBool = False

    @app.patch("/api/projects/{project_id}/editor/entry")
    def editor_rename_entry(project_id: str, request: EntryRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        try:
            target = entry_path(project.path, request.path)
            if project.read_only and (
                target == manager.data_dir
                or target in manager.data_dir.parents
                or manager.data_dir in target.parents
            ):
                raise ExplorerError("Protected Studio data")
            return rename_entry(project.path, request.path, request.name or "")
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    class DirectoryRequest(BaseModel):
        path: str = Field(min_length=1, max_length=500)
        authorize_existing: StrictBool = False

    class MoveRequest(DirectoryRequest):
        parent: str = Field(max_length=500)

    def protect_studio(target):
        data = manager.data_dir.resolve()
        if target == data or target in data.parents or data in target.parents:
            raise ExplorerError("Protected Studio data")

    @app.post("/api/projects/{project_id}/editor/directory")
    def editor_create_directory(project_id: str, request: DirectoryRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        try:
            if project.read_only:
                protect_studio(
                    safe_path(project.path, request.path, allow_missing=True)
                )
            return create_directory(project.path, request.path)
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.patch("/api/projects/{project_id}/editor/move")
    def editor_move_entry(project_id: str, request: MoveRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        try:
            source = entry_path(project.path, request.path)
            destination = directory_path(project.path, request.parent) / source.name
            if project.read_only:
                protect_studio(source)
                protect_studio(destination)
            if source == destination:
                return {"path": request.path}
            return workspaces.move_resource(
                project_id,
                lambda: move_entry(project.path, request.path, request.parent),
            )
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError, WorkspaceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/projects/{project_id}/editor/entry")
    def editor_delete_entry(project_id: str, request: EntryRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        if not request.confirmed:
            raise HTTPException(status_code=400, detail="Confirmation required")
        try:
            target = entry_path(project.path, request.path)
            if project.read_only and (
                target == manager.data_dir
                or target in manager.data_dir.parents
                or manager.data_dir in target.parents
            ):
                raise ExplorerError("Protected Studio data")
            return delete_entry(project.path, request.path)
        except (ExplorerError, OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    class BatchEntryRequest(BaseModel):
        paths: list[str] = Field(min_length=1, max_length=500)
        parent: str | None = Field(default=None, max_length=500)
        authorize_existing: StrictBool = False
        confirmed: StrictBool = False

    @app.post("/api/projects/{project_id}/editor/batch")
    def editor_batch(project_id: str, request: BatchEntryRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        if request.parent is None and not request.confirmed:
            raise HTTPException(status_code=400, detail="Confirmation required")
        try:
            return workspaces.move_resource(
                project_id,
                lambda: batch_entries(
                    project.path,
                    request.paths,
                    request.parent,
                    protect_studio if project.read_only else lambda target: None,
                ),
            )
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError, WorkspaceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/editor/copy")
    def editor_copy(project_id: str, request: BatchEntryRequest) -> dict:
        project = editable_project(project_id, request.authorize_existing)
        if request.parent is None:
            raise HTTPException(status_code=422, detail="Destination required")
        try:
            return workspaces.move_resource(
                project_id,
                lambda: copy_entries(
                    project.path,
                    request.paths,
                    request.parent,
                    protect_studio if project.read_only else lambda target: None,
                ),
            )
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ExplorerError, OSError, ValueError, WorkspaceError) as exc:
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

    class ProposalRequest(BaseModel):
        task: str = Field(min_length=1, max_length=4000)
        context_paths: list[str] = Field(default_factory=list, max_length=8)
        context_digest: str | None = None

    @app.post(
        "/api/projects/{project_id}/proposals", status_code=status.HTTP_202_ACCEPTED
    )
    def create_proposal(project_id: str, request: ProposalRequest) -> dict:
        try:
            return workspaces.submit(
                project_id, request.task, request.context_paths, request.context_digest
            )
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
        approved: StrictBool
        allow_existing: StrictBool = False

    class TestApproval(BaseModel):
        approval: str

    @app.get("/api/proposals/{proposal_id}/test")
    def preview_test(proposal_id: str) -> dict:
        try:
            return workspaces.test_preview(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/proposals/{proposal_id}/test")
    def test_proposal(proposal_id: str, request: TestApproval) -> dict:
        try:
            return workspaces.test(proposal_id, request.approval)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/proposals/{proposal_id}/repair")
    def repair_proposal(proposal_id: str) -> dict:
        try:
            return workspaces.repair(proposal_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    class GenerationDecision(BaseModel):
        retry: StrictBool
        context_paths: list[str] | None = Field(default=None, max_length=8)
        context_digest: str | None = None

    @app.post("/api/proposals/{proposal_id}/generation-decision")
    def generation_decision(proposal_id: str, request: GenerationDecision) -> dict:
        try:
            return workspaces.retry_generation(
                proposal_id,
                request.retry,
                request.context_paths,
                request.context_digest,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    class DeferRequest(BaseModel):
        action: str

    @app.post("/api/proposals/{proposal_id}/defer")
    def defer_proposal(proposal_id: str, request: DeferRequest) -> dict:
        try:
            return workspaces.defer(proposal_id, request.action)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/proposals/{proposal_id}/apply")
    def apply_proposal(proposal_id: str, request: ApplyRequest) -> dict:
        try:
            return workspaces.apply(
                proposal_id, request.approved, request.allow_existing
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (WorkspaceError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
