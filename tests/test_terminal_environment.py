"""Project Python environments are scoped to newly started terminal processes."""

import os
from dataclasses import replace
from pathlib import Path

from cmf_dev_studio.api.terminal import terminal_environment
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage


def make_venv(root: Path) -> Path:
    executable = root / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.touch()
    executable.chmod(0o755)
    (root / "pyvenv.cfg").write_text("version = 3.12.4\n")
    return executable


def test_terminal_uses_project_environment(tmp_path, monkeypatch):
    """Project Python takes priority without changing the parent environment."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    executable = make_venv(project.path / ".venv")
    monkeypatch.setenv("PATH", "/ide/bin:/usr/bin")
    monkeypatch.setenv("VIRTUAL_ENV", "/ide")
    monkeypatch.setenv("PYTHONHOME", "/ide")
    env = terminal_environment(project)
    assert env["PATH"] == f"{executable.parent}:/usr/bin"
    assert env["VIRTUAL_ENV"] == str(executable.parent.parent)
    assert "PYTHONHOME" not in env
    assert os.environ["PATH"] == "/ide/bin:/usr/bin"
    assert os.environ["VIRTUAL_ENV"] == "/ide"


def test_selected_environment_takes_priority(tmp_path):
    """An explicit interpreter wins over the automatically detected venv."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    make_venv(project.path / ".venv")
    selected = make_venv(tmp_path / "custom")
    project = replace(project, python_interpreter=str(selected))
    env = terminal_environment(project)
    assert env["PATH"].split(os.pathsep)[0] == str(selected.parent)
    assert env["VIRTUAL_ENV"] == str(selected.parent.parent)


def test_system_interpreter_is_not_a_virtual_environment(tmp_path, monkeypatch):
    """A selected system interpreter does not inherit the IDE's virtual environment."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    executable = tmp_path / "bin" / "python"
    executable.parent.mkdir()
    executable.touch()
    executable.chmod(0o755)
    monkeypatch.setenv("VIRTUAL_ENV", "/ide")
    env = terminal_environment(replace(project, python_interpreter=str(executable)))
    assert env["PATH"].split(os.pathsep)[0] == str(executable.parent)
    assert "VIRTUAL_ENV" not in env


def test_unconfigured_and_non_python_projects_keep_existing_environment(tmp_path):
    """No interpreter or a non-Python project preserves existing shell behavior."""
    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language=ProjectLanguage.PYTHON)
    expected = {**os.environ, "TERM": "xterm-256color"}
    assert terminal_environment(project) == expected
    make_venv(project.path / ".venv")
    for language in (ProjectLanguage.JAVA, ProjectLanguage.KOTLIN):
        assert terminal_environment(replace(project, language=language)) == expected
    missing = replace(project, python_interpreter="/missing/python")
    assert terminal_environment(missing) == expected
