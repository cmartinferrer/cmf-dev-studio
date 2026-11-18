"""Project environment detection, explicit creation and interpreter selection."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage
from cmf_dev_studio.projects.python_environment import (
    create_environment,
    environment_info,
    select_interpreter,
)


def test_detection_does_not_execute_interpreter(tmp_path):
    """Opening a project reads venv metadata without executing code."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    root = project.path / ".venv"
    executable = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    executable.parent.mkdir(parents=True)
    executable.write_text("not a real executable")
    executable.chmod(0o755)
    (root / "pyvenv.cfg").write_text("version = 3.12.4\n")
    with patch("subprocess.run") as run:
        info = environment_info(project)
    run.assert_not_called()
    assert info["available"] and info["version"] == "3.12.4"
    assert info["source"] == "detected"


def test_creation_uses_uv_and_preserves_existing_environment(tmp_path):
    """Creation uses an explicit target and never overwrites an existing venv."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    with (
        patch("shutil.which", return_value="/usr/bin/uv"),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run,
    ):
        create_environment(project)
        assert run.call_args.args[0][-2:] == [
            "--allow-existing",
            str(project.path / ".venv"),
        ]
        assert run.call_args.kwargs["cwd"] == project.path
        with pytest.raises(ValueError, match="already exists"):
            create_environment(project)
        assert run.call_count == 1


def test_missing_uv(tmp_path):
    """Missing uv is reported without running a command."""
    project = ProjectManager(tmp_path).create("Demo")
    with (
        patch("shutil.which", return_value=None),
        pytest.raises(ValueError, match="uv is not installed"),
    ):
        create_environment(project)


def test_select_real_interpreter():
    """An explicitly selected Python reports its version; relative paths fail."""
    path, version = select_interpreter(sys.executable)
    assert Path(path) == Path(sys.executable)
    assert version.startswith(f"{sys.version_info.major}.{sys.version_info.minor}.")
    with pytest.raises(ValueError, match="absolute path"):
        select_interpreter("python")


def test_environment_http_contract(tmp_path):
    """Selection is confirmed, persisted, scoped and resettable."""
    from cmf_dev_studio.api.app import create_app

    data = tmp_path / "studio"
    with TestClient(create_app(data)) as client:
        project = client.post(
            "/api/projects", json={"name": "Python", "language": "python"}
        ).json()
        other = client.post(
            "/api/projects", json={"name": "Java", "language": "java"}
        ).json()
        url = f"/api/projects/{project['id']}/python-environment"
        other_url = f"/api/projects/{other['id']}/python-environment"
        assert client.get(url).json()["source"] == "none"
        assert client.post(url, json={"action": "create"}).status_code == 400
        assert (
            client.post(
                other_url, json={"action": "create", "confirmed": True}
            ).status_code
            == 422
        )
        assert (
            client.post(
                url, json={"action": "select", "path": "python", "confirmed": True}
            ).status_code
            == 422
        )
        result = client.post(
            url, json={"action": "select", "path": sys.executable, "confirmed": True}
        )
        assert result.status_code == 200
        assert result.json()["source"] == "selected"
    with TestClient(create_app(data)) as client:
        assert client.get(url).json()["path"] == sys.executable
        assert client.get(other_url).json()["supported"] is False
        assert (
            client.post(url, json={"action": "reset", "confirmed": True}).json()[
                "source"
            ]
            == "none"
        )
        assert client.get("/api/projects/missing/python-environment").status_code == 404


def test_auto_language_updates_when_python_is_selected(tmp_path):
    """An explicitly configured Python environment updates project metadata."""
    from cmf_dev_studio.api.app import create_app

    root = tmp_path / "external"
    root.mkdir()
    (root / "main.py").write_text("print('hello')")
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post(
            "/api/projects/register",
            json={"path": str(root), "name": "ignored", "description": "ignored"},
        ).json()
        assert project["name"] == "external"
        assert project["description"] == ""
        url = f"/api/projects/{project['id']}"
        result = client.post(
            url + "/python-environment",
            json={"action": "select", "path": sys.executable, "confirmed": True},
        )
        assert result.status_code == 200
        assert client.get(url).json()["language"] == "python"
