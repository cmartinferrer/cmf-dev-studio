"""Verify project JDK execution and environment-bound approvals."""

import os
import sys
from pathlib import Path

import pytest

from cmf_dev_studio import workspaces
from cmf_dev_studio.project_runners import RunnerSpec, execute_runner
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


def fake_jdk(home: Path, version: str) -> Path:
    """Create a discoverable JDK without requiring Java installation."""
    (home / "bin").mkdir(parents=True)
    for name in ("java", "javac"):
        executable = home / "bin" / name
        executable.touch()
        executable.chmod(0o755)
    (home / "release").write_text(f'JAVA_VERSION="{version}"\n')
    return home


@pytest.mark.parametrize("runner", ["maven", "gradle"])
def test_runner_uses_project_jdk(tmp_path, monkeypatch, runner):
    """Override inherited Java settings only inside the child process."""
    selected = fake_jdk(tmp_path / "selected jdk", "17")
    monkeypatch.setenv("JAVA_HOME", "/system/jdk")
    original_path = os.environ["PATH"]
    workspace = tmp_path / "project"
    workspace.mkdir()
    command = (
        sys.executable,
        "-c",
        (
            "import os; print(os.environ['JAVA_HOME']); "
            "print(os.environ['PATH'].split(os.pathsep)[0])"
        ),
    )
    passed, output = execute_runner(
        workspace, RunnerSpec(runner, command, jdk_home=str(selected))
    )
    assert passed, output
    assert output.splitlines()[-2:] == [str(selected), str(selected / "bin")]
    assert os.environ["JAVA_HOME"] == "/system/jdk"
    assert os.environ["PATH"] == original_path


@pytest.mark.parametrize(
    ("language", "manifest", "source", "runner"),
    [
        ("java", "pom.xml", "Example.java", "maven"),
        ("kotlin", "build.gradle.kts", "Example.kt", "gradle"),
        ("auto", "pom.xml", "Example.java", "maven"),
    ],
)
def test_jdk_change_requires_new_approval(
    tmp_path, monkeypatch, language, manifest, source, runner
):
    """Bind approval to the selected JDK even when the command is unchanged."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", language=language, location=tmp_path)
    first = fake_jdk(tmp_path / "jdk17", "17")
    second = fake_jdk(tmp_path / "jdk21", "21")
    manager.update_jdk(project.id, str(first))
    service = WorkspaceService(manager)
    pid = "a" * 32
    workspace = service.root / pid
    tests = workspace / "src/test"
    tests.mkdir(parents=True)
    (tests / source).touch()
    (workspace / manifest).touch()
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "ready", "task", "now"),
        )
    original = service.test_preview(pid)
    manager.update_jdk(project.id, str(second))
    with pytest.raises(WorkspaceError, match="Explicit approval"):
        service.test(pid, original["approval"])
    approved = service.test_preview(pid)
    specs = []

    def run(_workspace, spec):
        specs.append(spec)
        return True, "passed"

    monkeypatch.setattr(workspaces, "execute_runner", run)
    assert service.test(pid, approved["approval"])["status"] == "tested"
    assert specs[0].name == runner
    assert specs[0].jdk_home == str(second)
    assert specs[0].jdk_version == "21"
    manager.update_jdk(project.id, str(tmp_path / "missing"))
    with pytest.raises(WorkspaceError, match="No available JDK"):
        service.test_preview(pid)
