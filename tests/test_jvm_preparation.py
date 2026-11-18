"""Verify approved JVM builds use the real project and selected JDK."""

import sys
from unittest.mock import patch

import pytest

from cmf_dev_studio.project_runners import RunnerSpec, execute_runner
from cmf_dev_studio.projects.jvm_preparation import preparation_spec, prepare_jvm
from cmf_dev_studio.projects.models import Project, ProjectKind, ProjectLanguage


@pytest.mark.parametrize(
    ("language", "manifest", "wrapper", "tool"),
    [
        (ProjectLanguage.JAVA, "pom.xml", "mvnw", "maven"),
        (ProjectLanguage.KOTLIN, "build.gradle.kts", "gradlew", "gradle"),
    ],
)
def test_prepare_jvm(tmp_path, language, manifest, wrapper, tool):
    """Prefer wrappers and build in place with the chosen JDK."""
    project = Project("id", "demo", tmp_path, ProjectKind.MANAGED, "", "", language)
    (tmp_path / manifest).touch()
    (tmp_path / wrapper).touch()
    spec = preparation_spec(project)
    assert spec.name == tool
    assert spec.command[:2] == ("sh", f"./{wrapper}")
    with (
        patch(
            "cmf_dev_studio.projects.jvm_preparation.environment_info",
            return_value={"current": {"path": "/jdk", "version": "21"}},
        ),
        patch(
            "cmf_dev_studio.projects.jvm_preparation.execute_runner",
            return_value=(True, "ok"),
        ) as run,
    ):
        assert prepare_jvm(project) == "ok"
    assert run.call_args.args[0] == tmp_path
    assert run.call_args.args[1].jdk_home == "/jdk"
    assert run.call_args.kwargs == {"in_place": True}


def test_existing_project_can_be_prepared(tmp_path):
    """Offer the same preparation for registered repositories."""
    project = Project(
        "id", "demo", tmp_path, ProjectKind.EXISTING, "", "", ProjectLanguage.JAVA
    )
    (tmp_path / "pom.xml").touch()
    assert preparation_spec(project) is not None


def test_runner_in_place(tmp_path):
    """Only explicit in-place execution leaves generated artifacts behind."""
    spec = RunnerSpec("test", (sys.executable, "-c", "open('artifact', 'w').close()"))
    assert execute_runner(tmp_path, spec)[0]
    assert not (tmp_path / "artifact").exists()
    assert execute_runner(tmp_path, spec, in_place=True)[0]
    assert (tmp_path / "artifact").exists()


@pytest.mark.parametrize("confirmed", [True, False])
def test_jvm_preparation_approval(tmp_path, confirmed):
    """Persist approval or refusal without executing an unapproved build."""
    from cmf_dev_studio.projects.manager import ProjectManager
    from cmf_dev_studio.workspaces import WorkspaceService

    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language=ProjectLanguage.JAVA)
    service = WorkspaceService(manager)
    pid = "a" * 32
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) "
            "VALUES (?,?,?,?,?)",
            (pid, project.id, "applied", "task", "now"),
        )
        service._event(db, pid, "environment_offered", environment="jvm")
    with patch("cmf_dev_studio.workspaces.prepare_jvm") as prepare:
        result = service.prepare_python(pid, confirmed)
    assert prepare.call_count == int(confirmed)
    assert result["events"][-1]["kind"] == (
        "environment_ready" if confirmed else "environment_skipped"
    )
