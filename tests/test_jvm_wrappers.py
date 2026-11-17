"""Verify wrapper selection, snapshot preservation and local execution."""

from dataclasses import replace

import pytest

from cmf_dev_studio.project_runners import RunnerSpec, execute_runner, select_runner
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import (
    WorkspaceError,
    WorkspaceService,
    safe_path,
    snapshot,
)


@pytest.mark.parametrize(
    ("manifest", "script", "properties", "jar", "tool"),
    [
        (
            "pom.xml",
            "mvnw",
            ".mvn/wrapper/maven-wrapper.properties",
            ".mvn/wrapper/maven-wrapper.jar",
            "mvn",
        ),
        (
            "build.gradle.kts",
            "gradlew",
            "gradle/wrapper/gradle-wrapper.properties",
            "gradle/wrapper/gradle-wrapper.jar",
            "gradle",
        ),
    ],
)
def test_wrapper_survives_snapshot_and_rebuild(
    tmp_path, manifest, script, properties, jar, tool
):
    """Preserve binary assets through proposal rebuild and prefer the wrapper."""
    source = tmp_path / "source"
    source.mkdir()
    (source / manifest).touch()
    (source / "src/test").mkdir(parents=True)
    (source / "src/test/Example.java").touch()
    assert select_runner(source).command[0] == tool
    (source / script).write_text('printf "%s\\n" "$JAVA_HOME" "$@"\n')
    for name, data in [(properties, b"distributionUrl=example"), (jar, b"\xff\x00")]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (source / ".mvn").mkdir(exist_ok=True)
    (source / ".mvn/secret.txt").write_text("secret")
    (source / "other.jar").write_bytes(b"\xff")
    service = WorkspaceService(ProjectManager(tmp_path / "data"))
    workspace = service.root / "proposal"
    workspace.mkdir()
    original = snapshot(source, workspace)
    assert original[jar] == b"\xff\x00"
    assert ".mvn/secret.txt" not in original
    assert "other.jar" not in original
    service._write_operations("proposal", [], original)
    assert (workspace / jar).read_bytes() == b"\xff\x00"
    spec = select_runner(workspace)
    assert spec.command[:2] == ("sh", f"./{script}")
    passed, output = execute_runner(workspace, replace(spec, jdk_home="/selected/jdk"))
    assert passed, output
    assert "/selected/jdk" in output
    assert "test" in output
    with pytest.raises(WorkspaceError):
        safe_path(jar)


def test_incomplete_wrapper_is_infrastructure_error(tmp_path):
    """Do not silently fall back to global Gradle for an incomplete wrapper."""
    (tmp_path / "build.gradle").touch()
    (tmp_path / "gradlew").touch()
    (tmp_path / "src/test").mkdir(parents=True)
    (tmp_path / "src/test/Test.kt").touch()
    passed, output = execute_runner(tmp_path, select_runner(tmp_path))
    assert not passed
    assert "infrastructure_error" in output
    assert "gradle-wrapper.jar" in output


@pytest.mark.parametrize("tool", ["mvn", "gradle"])
def test_missing_build_tool_has_actionable_error(tmp_path, monkeypatch, tool):
    """Explain missing tools without attempting installation."""
    monkeypatch.setenv("PATH", str(tmp_path))
    passed, output = execute_runner(
        tmp_path, RunnerSpec("maven" if tool == "mvn" else "gradle", (tool, "test"))
    )
    assert not passed
    assert "infrastructure_error" in output
    assert "backend PATH" in output
