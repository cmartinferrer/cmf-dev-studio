"""HTTP contract tests; no Docker, Gemini, or running web server required."""

from fastapi.testclient import TestClient

from multi_agent_software_team.api.app import create_app


def test_health_and_empty_projects(tmp_path):
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/projects").json() == []


def test_create_list_and_get_persisted_project(tmp_path):
    data = tmp_path / "studio"
    with TestClient(create_app(data)) as client:
        result = client.post("/api/projects", json={"name": "Calculator", "description": "Demo"})
        assert result.status_code == 201
        project = result.json()
        assert project["kind"] == "managed"
        assert project["read_only"] is False
        assert project["name"] == "Calculator"
        assert client.get(f"/api/projects/{project['id']}").json() == project
    with TestClient(create_app(data)) as client:
        assert client.get("/api/projects").json() == [project]


def test_register_existing_is_read_only_and_does_not_modify_files(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "main.py"
    source.write_text("print('unchanged')\n")
    with TestClient(create_app(tmp_path / "studio")) as client:
        result = client.post("/api/projects/register", json={"path": str(repository)})
        assert result.status_code == 201
        project = result.json()
        assert project["kind"] == "existing"
        assert project["read_only"] is True
        assert project["path"] == str(repository.resolve())
    assert source.read_text() == "print('unchanged')\n"
    assert sorted(p.name for p in repository.iterdir()) == ["main.py"]


def test_invalid_create_and_missing_project(tmp_path):
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert client.post("/api/projects", json={"name": "../invalid"}).status_code == 422
        assert client.post("/api/projects", json={"name": ""}).status_code == 422
        assert client.get("/api/projects/nonexistent").status_code == 404


def test_invalid_register_and_duplicate_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert client.post("/api/projects/register", json={"path": str(tmp_path / 'missing')}).status_code == 422
        assert client.post("/api/projects/register", json={"path": str(repo)}).status_code == 201
        assert client.post("/api/projects/register", json={"path": str(repo)}).status_code == 422


def test_reject_registering_studio_data_directory(tmp_path):
    studio = tmp_path / "studio"
    with TestClient(create_app(studio)) as client:
        assert client.post("/api/projects/register", json={"path": str(studio)}).status_code == 422
