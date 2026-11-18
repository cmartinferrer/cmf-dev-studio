"""HTTP contract tests; no Docker, Gemini, or running web server required."""

from importlib.metadata import version

from fastapi.testclient import TestClient

from cmf_dev_studio.api.app import create_app


def test_health_and_empty_projects(tmp_path):
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/projects").json() == []


def test_create_list_and_get_persisted_project(tmp_path):
    data = tmp_path / "studio"
    with TestClient(create_app(data)) as client:
        result = client.post(
            "/api/projects", json={"name": "Calculator", "description": "Demo"}
        )
        assert result.status_code == 201
        project = result.json()
        assert project["kind"] == "managed"
        assert project["read_only"] is False
        assert project["name"] == "Calculator"
        assert client.get(f"/api/projects/{project['id']}").json() == project
    with TestClient(create_app(data)) as client:
        assert client.get("/api/projects").json() == [project]


def test_register_existing_is_editable_and_does_not_modify_files(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "main.py"
    source.write_text("print('unchanged')\n")
    with TestClient(create_app(tmp_path / "studio")) as client:
        result = client.post("/api/projects/register", json={"path": str(repository)})
        assert result.status_code == 201
        project = result.json()
        assert project["kind"] == "existing"
        assert project["read_only"] is False
        assert project["path"] == str(repository.resolve())
    assert source.read_text() == "print('unchanged')\n"
    assert sorted(p.name for p in repository.iterdir()) == ["main.py"]


def test_invalid_create_and_missing_project(tmp_path):
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert (
            client.post("/api/projects", json={"name": "../invalid"}).status_code == 422
        )
        assert client.post("/api/projects", json={"name": ""}).status_code == 422
        assert client.get("/api/projects/nonexistent").status_code == 404


def test_invalid_register_and_duplicate_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with TestClient(create_app(tmp_path / "studio")) as client:
        assert (
            client.post(
                "/api/projects/register", json={"path": str(tmp_path / "missing")}
            ).status_code
            == 422
        )
        assert (
            client.post("/api/projects/register", json={"path": str(repo)}).status_code
            == 201
        )
        assert (
            client.post("/api/projects/register", json={"path": str(repo)}).status_code
            == 422
        )


def test_reject_registering_studio_data_directory(tmp_path):
    studio = tmp_path / "studio"
    with TestClient(create_app(studio)) as client:
        assert (
            client.post(
                "/api/projects/register", json={"path": str(studio)}
            ).status_code
            == 422
        )


def test_project_language_http_contract(tmp_path):
    """Explicit languages round-trip through create, get and list; invalid values fail."""
    with TestClient(create_app(tmp_path / "studio")) as client:
        for language in ("python", "java", "kotlin"):
            response = client.post(
                "/api/projects", json={"name": language, "language": language}
            )
            assert response.status_code == 201
            project = response.json()
            assert project["language"] == language
            assert client.get("/api/projects/" + project["id"]).json() == project
        assert {p["language"] for p in client.get("/api/projects").json()} == {
            "python",
            "java",
            "kotlin",
        }
        assert (
            client.post(
                "/api/projects", json={"name": "bad", "language": "invalid"}
            ).status_code
            == 422
        )
        assert (
            client.post("/api/projects", json={"name": "legacy"}).json()["language"]
            == "auto"
        )


def test_update_project_language_http_contract(tmp_path):
    """Language updates are validated, persisted and scoped to one project."""
    data = tmp_path / "studio"
    with TestClient(create_app(data)) as client:
        project = client.post("/api/projects", json={"name": "Demo"}).json()
        other = client.post("/api/projects", json={"name": "Other"}).json()
        url = f"/api/projects/{project['id']}/language"
        for language in ("java", "kotlin", "python", "auto"):
            response = client.patch(url, json={"language": language})
            assert response.status_code == 200
            assert response.json() == {**project, "language": language}
        for payload in ({}, {"language": None}, {"language": "invalid"}):
            assert client.patch(url, json=payload).status_code == 422
        assert (
            client.patch(
                "/api/projects/missing/language", json={"language": "java"}
            ).status_code
            == 404
        )
        assert client.patch(url, json={"language": "kotlin"}).status_code == 200
        assert client.get(f"/api/projects/{other['id']}").json() == other
    with TestClient(create_app(data)) as client:
        assert client.get(f"/api/projects/{project['id']}").json() == {
            **project,
            "language": "kotlin",
        }


def test_api_version_matches_package_version(tmp_path):
    """Ensure the API version matches the installed package version."""
    app = create_app(tmp_path / "studio")

    assert app.version == version("cmf-dev-studio")


def test_open_project_cannot_be_removed_or_deleted(tmp_path):
    """Both deletion modes require a closed project."""
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post(
            "/api/projects", json={"name": "Local", "location": str(tmp_path)}
        ).json()
        url = "/api/projects/" + project["id"]
        assert client.post(url + "/open").status_code == 200
        for mode in ("false", "true"):
            assert (
                client.delete(url + "?confirmed=true&from_disk=" + mode).status_code
                == 409
            )
        assert client.post(url + "/close").status_code == 200
        assert client.delete(url + "?confirmed=true&from_disk=true").status_code == 200
        assert not (tmp_path / "Local").exists()


def test_multiple_workspace_sessions(tmp_path):
    """Closing one browser tab cannot unlock a project in another tab."""
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post("/api/projects", json={"name": "sample"}).json()
        url = f"/api/projects/{project['id']}"
        for session in ("one", "two"):
            assert (
                client.post(url + "/open", params={"session": session}).status_code
                == 200
            )
        assert client.post(url + "/close", params={"session": "one"}).status_code == 200
        assert (
            client.delete(
                url, params={"confirmed": True, "from_disk": True}
            ).status_code
            == 409
        )
        assert client.post(url + "/close", params={"session": "two"}).status_code == 200
        assert client.delete(url, params={"confirmed": True}).status_code == 200


def test_workspace_presence_disconnect(tmp_path):
    """A disconnected workspace releases its own presence lock."""
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post("/api/projects", json={"name": "sample"}).json()
        url = f"/api/projects/{project['id']}"
        with client.websocket_connect(url + "/presence?session=one"):
            assert client.delete(url, params={"confirmed": True}).status_code == 409
        assert client.delete(url, params={"confirmed": True}).status_code == 200
