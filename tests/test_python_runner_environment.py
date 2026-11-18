"""Verify isolated Python test commands and interpreter-bound approvals."""

import sys
from pathlib import Path

import pytest

from cmf_dev_studio import workspaces
from cmf_dev_studio.project_runners import select_runner
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


@pytest.mark.parametrize("manifest", [False, True])
def test_python_runner_isolated(tmp_path, manifest):
    """Use uv for scripts and packaged projects, with declared requirements."""
    (tmp_path / "test_main.py").touch()
    (tmp_path / "requirements.txt").touch()
    if manifest:
        (tmp_path / "pyproject.toml").touch()
    command = select_runner(tmp_path, sys.executable).command
    assert command[:4] == ("uv", "run", "--isolated", "--no-python-downloads")
    assert command[4:6] == ("--python", sys.executable)
    assert ("--no-project" in command) is not manifest
    assert command[command.index("--with-requirements") + 1] == "requirements.txt"
    assert command[-5:] == ("--", "python", "-m", "pytest", "-q")


def test_default_python_runner(tmp_path):
    """Let uv choose Python without falling back to the IDE interpreter."""
    (tmp_path / "test_main.py").touch()
    command = select_runner(tmp_path).command
    assert "--isolated" in command
    assert "--python" not in command
    assert "--with-requirements" not in command


def test_interpreter_change_invalidates_approval(tmp_path, monkeypatch):
    """Require approval again when the selected interpreter changes."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create(
        "sample", language=ProjectLanguage.PYTHON, location=tmp_path
    )
    service = WorkspaceService(manager)
    pid = "b" * 32
    workspace = service.root / pid
    workspace.mkdir()
    (workspace / "test_main.py").write_text("def test_main(): pass\n")
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "ready", "task", "now"),
        )
    original = service.test_preview(pid)
    manager.update_python_interpreter(project.id, sys.executable, "3.12.0")
    with pytest.raises(WorkspaceError, match="Explicit approval"):
        service.test(pid, original["approval"])
    approved = service.test_preview(pid)
    commands = []

    def run(_workspace, spec):
        commands.append(list(spec.command))
        return True, "passed"

    monkeypatch.setattr(workspaces, "execute_runner", run)
    assert service.test(pid, approved["approval"])["status"] == "tested"
    assert commands == [approved["command"]]
    assert str(Path(sys.executable)) in commands[0]
