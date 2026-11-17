"""JDK discovery and project-specific selection contracts."""

from fastapi.testclient import TestClient

from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.projects import ProjectManager
from cmf_dev_studio.projects.jdk_environment import environment_info, inspect_jdk


def fake_jdk(root, version):
    """Create metadata and executable placeholders; never execute them."""
    (root / "bin").mkdir(parents=True)
    for name in ("java", "javac"):
        executable = root / "bin" / name
        executable.touch()
        executable.chmod(0o755)
    (root / "release").write_text(f'JAVA_VERSION="{version}"\n')
    return root


def test_inspect_jdk_requires_compiler(tmp_path):
    home = fake_jdk(tmp_path / "jdk", "21.0.1")
    assert inspect_jdk(home) == {"path": str(home), "version": "21.0.1"}
    (home / "bin/javac").unlink()
    assert inspect_jdk(home) is None


def test_selection_persists_and_is_scoped(tmp_path, monkeypatch):
    home = fake_jdk(tmp_path / "jdk", "17.0.1")
    monkeypatch.setattr("cmf_dev_studio.projects.jdk_environment.discover_jdks", list)
    data = tmp_path / "studio"
    manager = ProjectManager(data)
    with TestClient(create_app(data)) as client:
        java = client.post(
            "/api/projects", json={"name": "Java", "language": "java"}
        ).json()
        kotlin = client.post(
            "/api/projects", json={"name": "Kotlin", "language": "kotlin"}
        ).json()
        url = f"/api/projects/{java['id']}/jdk"
        assert (
            client.post(url, json={"path": str(home)}).json()["current"]["version"]
            == "17.0.1"
        )
        assert client.get(f"/api/projects/{kotlin['id']}/jdk").json()["current"] is None
        assert client.post(url, json={"path": "relative"}).status_code == 422
        assert manager.get(java["id"]).jdk_home == str(home)
        assert client.post(url, json={"path": None}).json()["current"] is None


def test_default_and_missing_selection(tmp_path, monkeypatch):
    home = fake_jdk(tmp_path / "jdk", "21")
    monkeypatch.setattr(
        "cmf_dev_studio.projects.jdk_environment.discover_jdks",
        lambda: [inspect_jdk(home)],
    )
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("Demo", language="kotlin")
    assert environment_info(project)["source"] == "detected"
    project = manager.update_jdk(project.id, str(tmp_path / "missing"))
    assert environment_info(project)["current"] is None
