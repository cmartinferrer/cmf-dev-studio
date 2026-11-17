"""Approved dependency setup targets only the real project's local environment."""

import subprocess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage
from cmf_dev_studio.projects.python_environment import (
    _venv_python,
    preparation_needed,
    prepare_environment,
)
from cmf_dev_studio.workspaces import WorkspaceService


def test_install_targets_project_environment(tmp_path):
    """Use an explicit interpreter and keep the IDE environment out of uv."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    root = project.path / ".venv"
    python = _venv_python(root)
    python.parent.mkdir(parents=True)
    python.touch()
    python.chmod(0o755)
    (root / "pyvenv.cfg").touch()
    (project.path / "requirements.txt").write_text("requests\n")
    with (
        patch("shutil.which", return_value="/usr/bin/uv"),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run,
    ):
        prepare_environment(project)
    assert run.call_args.args[0] == [
        "/usr/bin/uv",
        "pip",
        "install",
        "--python",
        str(python),
        "-r",
        "requirements.txt",
    ]
    assert "VIRTUAL_ENV" not in run.call_args.kwargs["env"]
    assert preparation_needed(project, [{"path": "requirements.txt"}])
    assert not preparation_needed(project, [{"path": "main.py"}])


def test_external_interpreter_is_not_modified(tmp_path):
    """Never install into a custom system or shared interpreter."""
    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language=ProjectLanguage.PYTHON)
    project = manager.update_python_interpreter(project.id, "/usr/bin/python3", "3.12")
    assert not preparation_needed(project, [])
    with (
        patch("subprocess.run") as run,
        pytest.raises(ValueError, match="Select the project"),
    ):
        prepare_environment(project)
    run.assert_not_called()


@pytest.mark.parametrize("confirmed", [True, False])
def test_preparation_decision_persists(tmp_path, confirmed):
    """Require a pending applied proposal and persist the decision and result."""
    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language=ProjectLanguage.PYTHON)
    service = WorkspaceService(manager)
    pid = "a" * 32
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "applied", "task", "now"),
        )
        service._event(db, pid, "environment_offered")
    url = f"/api/proposals/{pid}/prepare-python"
    with (
        TestClient(create_app(tmp_path)) as client,
        patch("cmf_dev_studio.workspaces.prepare_environment") as prepare,
    ):
        assert client.post(url, json={}).status_code == 422
        assert client.post(url, json={"confirmed": "true"}).status_code == 422
        result = client.post(url, json={"confirmed": confirmed})
        assert result.status_code == 200
        assert prepare.call_count == int(confirmed)
        assert client.post(url, json={"confirmed": True}).status_code == 409
    events = service.get(pid)["events"]
    assert events[-1]["kind"] == (
        "environment_ready" if confirmed else "environment_skipped"
    )


def test_apply_offers_preparation_without_installing(tmp_path, monkeypatch):
    """Applying Python files offers setup but does not execute installation."""
    from cmf_dev_studio import workspaces

    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language=ProjectLanguage.PYTHON)
    service = WorkspaceService(manager)
    pid = "b" * 32
    workspace = service.root / pid
    workspace.mkdir()
    (workspace / "test_sample.py").write_text("def test_sample(): pass\n")
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "queued", "task", "now"),
        )
    service._update(
        pid,
        "ready",
        changes=[{"action": "create", "path": "test_sample.py", "before_sha256": None}],
    )
    monkeypatch.setattr(workspaces, "execute_runner", lambda *_: (True, "success"))
    service.test(pid, service.test_preview(pid)["approval"])
    with patch("cmf_dev_studio.workspaces.prepare_environment") as prepare:
        result = service.apply(pid, True)
    prepare.assert_not_called()
    assert result["events"][-1]["kind"] == "environment_offered"
    assert not (project.path / ".venv").exists()
