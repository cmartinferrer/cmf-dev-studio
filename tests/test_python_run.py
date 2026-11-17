"""Run saved Python files with the project interpreter, never through a shell."""

import sys
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.api.terminal import python_run_command
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage


def test_run_command_uses_exact_interpreter_and_path(tmp_path):
    """Spaces and shell metacharacters remain literal arguments."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    project = replace(project, python_interpreter=sys.executable)
    path = project.path / "a; b.py"
    path.write_text("print('ok')")
    assert python_run_command(project, path.name) == [sys.executable, "-u", str(path)]


def test_run_rejects_missing_environment_and_unsafe_paths(tmp_path):
    """Only saved Python files inside the project may be run."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    (project.path / "main.py").touch()
    with pytest.raises(ValueError, match="Set up Python"):
        python_run_command(project, "main.py")
    project = replace(project, python_interpreter=sys.executable)
    (project.path / "notes.txt").touch()
    (project.path / "link.py").symlink_to(project.path / "main.py")
    for path in ("../main.py", "missing.py", "notes.txt", "link.py"):
        with pytest.raises(ValueError):
            python_run_command(project, path)


def test_run_websocket_streams_output_and_exit(tmp_path):
    """A real short-lived script produces output and a completion message."""
    data = tmp_path / "studio"
    manager = ProjectManager(data)
    project = manager.create("Demo", language=ProjectLanguage.PYTHON)
    # A symlink is normal for a virtual environment's Python executable.
    executable = project.path / ".venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(sys.executable)
    (project.path / "main.py").write_text("print('run-ok')\n")
    with (
        TestClient(create_app(data), base_url="http://localhost:8000") as client,
        client.websocket_connect(
            f"/api/projects/{project.id}/terminal?run=main.py",
            headers={"origin": "http://localhost:8000", "host": "localhost:8000"},
        ) as ws,
    ):
        output = ""
        while True:
            event = ws.receive()
            if event["type"] == "websocket.close":
                break
            output += event.get("text", "") + event.get("bytes", b"").decode()
    assert "Running Python file: 'main.py'" in output
    assert output.index("Running Python file") < output.index("run-ok")
    assert "run-ok" in output
    assert "Process exited with code 0" in output
