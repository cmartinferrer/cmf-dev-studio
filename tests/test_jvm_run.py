"""Editor execution resolves saved JVM sources and project build tools."""

import pytest

from cmf_dev_studio.projects import jvm_run
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Use a deterministic JDK selection without installing tools."""
    monkeypatch.setattr(
        jvm_run,
        "environment_info",
        lambda _: {"current": {"path": "/jdk", "version": "21"}},
    )
    return ProjectManager(tmp_path / "studio").create(
        "Demo", language=ProjectLanguage.JAVA, location=tmp_path
    )


def write_source(project, path, source):
    """Create a conventional source file."""
    target = project.path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    return path


def test_maven_main(project, tmp_path):
    """Maven compiles and launches the qualified class with the selected JDK."""
    (project.path / "pom.xml").touch()
    (project.path / "mvnw").touch()
    path = write_source(
        project,
        "src/main/java/demo/Main.java",
        "package demo;\npublic class Main { public static void main(String[] args) {} }",
    )
    command = jvm_run.jvm_run_command(project, path, tmp_path)
    assert command[:4] == ["sh", "./mvnw", "-B", "compile"]
    assert "-Dexec.executable=/jdk/bin/java" in command
    assert command[-1] == "-Dexec.args=-classpath %classpath demo.Main"


def test_gradle_kotlin_main(project, tmp_path):
    """Gradle uses an external init script without editing the build."""
    (project.path / "build.gradle.kts").touch()
    (project.path / "gradlew").touch()
    path = write_source(
        project, "src/main/kotlin/demo/Main.kt", "package demo\nfun main() {}"
    )
    command = jvm_run.jvm_run_command(project, path, tmp_path)
    assert command[:2] == ["sh", "./gradlew"]
    assert "-PcmfEditorMain=demo.MainKt" in command
    assert "runtimeClasspath" in (tmp_path / "cmf-run.gradle").read_text()
    assert not (project.path / "cmf-run.gradle").exists()


@pytest.mark.parametrize(
    "build,expected",
    [
        ("pom.xml", "-Dtest=demo.CalculatorTest"),
        ("build.gradle.kts", "demo.CalculatorTest"),
    ],
)
def test_run_test_class(project, tmp_path, build, expected):
    """Only the selected test class is requested."""
    (project.path / build).touch()
    path = write_source(
        project,
        "src/test/java/demo/CalculatorTest.java",
        "package demo;\nclass CalculatorTest {}",
    )
    assert expected in jvm_run.jvm_run_command(project, path, tmp_path)


def test_reject_helper_and_unsafe_path(project, tmp_path):
    """Helpers and traversal paths cannot be launched."""
    path = write_source(project, "src/main/java/Helper.java", "class Helper {}")
    with pytest.raises(ValueError, match="no supported main"):
        jvm_run.jvm_run_command(project, path, tmp_path)
    with pytest.raises(ValueError):
        jvm_run.jvm_run_command(project, "../Helper.java", tmp_path)


def test_websocket_runs_wrapper(tmp_path, monkeypatch):
    """A real wrapper process streams output through the existing terminal."""
    from fastapi.testclient import TestClient

    from cmf_dev_studio.api import terminal
    from cmf_dev_studio.api.app import create_app

    data = tmp_path / "studio"
    project = ProjectManager(data).create(
        "Demo", language=ProjectLanguage.JAVA, location=tmp_path
    )
    jdk = {"path": "/jdk", "version": "21"}
    monkeypatch.setattr(jvm_run, "environment_info", lambda _: {"current": jdk})
    monkeypatch.setattr(
        terminal, "jdk_info", lambda _: {"supported": True, "current": jdk}
    )
    (project.path / "pom.xml").touch()
    (project.path / "mvnw").write_text('printf "jdk=%s\\n" "$JAVA_HOME"\n')
    path = write_source(
        project,
        "src/main/java/Main.java",
        "class Main { public static void main(String[] args) {} }",
    )
    with (
        TestClient(create_app(data), base_url="http://localhost:8000") as client,
        client.websocket_connect(
            f"/api/projects/{project.id}/terminal?run={path}",
            headers={"origin": "http://localhost:8000", "host": "localhost:8000"},
        ) as ws,
    ):
        output = ""
        while True:
            event = ws.receive()
            if event["type"] == "websocket.close":
                break
            output += event.get("text", "") + event.get("bytes", b"").decode()
    assert "Running Java file" in output
    assert "jdk=/jdk" in output
    assert "Process exited with code 0" in output
