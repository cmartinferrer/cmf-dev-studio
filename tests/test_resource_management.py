"""Regression tests for explicit project and filesystem management."""

import pytest

from cmf_dev_studio.projects.editor import EditConflict, delete_entry, rename_entry
from cmf_dev_studio.projects.explorer import ExplorerError
from cmf_dev_studio.projects.manager import ProjectManager


def test_project_rename_preserves_identity_and_files(tmp_path):
    """Display names never relocate the project or its files."""
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("Old")
    (project.path / "main.py").write_text("hello")
    renamed = manager.rename(project.id, "New")
    assert renamed.id == project.id and renamed.path == project.path
    assert ProjectManager(manager.data_dir).get(project.id).name == "New"
    assert (project.path / "main.py").read_text() == "hello"


def test_delete_managed_and_unregister_external(tmp_path):
    """Only managed workspaces are removed from disk."""
    manager = ProjectManager(tmp_path / "studio")
    managed = manager.create("Managed")
    external = tmp_path / "external"
    external.mkdir()
    (external / "main.py").write_text("keep")
    registered = manager.register_existing(external)
    assert manager.delete(managed.id) and not managed.path.exists()
    assert manager.delete(registered.id) and (external / "main.py").exists()
    assert manager.list_projects() == []


def test_rename_and_delete_folder(tmp_path):
    """Folder operations preserve nested content until explicitly deleted."""
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "a.py").write_text("hello")
    assert rename_entry(tmp_path, "src/a.py", "b.py")["path"] == "src/b.py"
    assert rename_entry(tmp_path, "src", "code")["path"] == "code"
    assert (tmp_path / "code/b.py").read_text() == "hello"
    assert delete_entry(tmp_path, "code")["deleted"]
    assert not (tmp_path / "code").exists()


@pytest.mark.parametrize("name", ["../escape", ".git", "a/b", "a\\b", ""])
def test_invalid_names(tmp_path, name):
    """Names cannot escape the parent or target protected entries."""
    (tmp_path / "a").touch()
    with pytest.raises(ExplorerError):
        rename_entry(tmp_path, "a", name)


def test_collision_and_symlink(tmp_path):
    """Existing targets and symbolic links cannot be overwritten or followed."""
    (tmp_path / "a").touch()
    (tmp_path / "b").touch()
    (tmp_path / "link").symlink_to(tmp_path / "b")
    with pytest.raises(EditConflict):
        rename_entry(tmp_path, "a", "b")
    with pytest.raises(ExplorerError):
        delete_entry(tmp_path, "link")
    assert (tmp_path / "b").exists()


def test_api_resource_permissions(tmp_path):
    """External writes and destructive actions require explicit authorization."""
    from fastapi.testclient import TestClient

    from cmf_dev_studio.api.app import create_app

    external = tmp_path / "repo"
    external.mkdir()
    (external / "a.py").touch()
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post(
            "/api/projects/register", json={"path": str(external)}
        ).json()
        url = "/api/projects/" + project["id"]
        assert client.patch(url + "/name", json={"name": "Renamed"}).status_code == 200
        assert (
            client.patch(
                url + "/editor/entry", json={"path": "a.py", "name": "b.py"}
            ).status_code
            == 403
        )
        assert (
            client.patch(
                url + "/editor/entry",
                json={"path": "a.py", "name": "b.py", "authorize_existing": True},
            ).status_code
            == 200
        )
        assert (
            client.request(
                "DELETE",
                url + "/editor/entry",
                json={"path": "b.py", "authorize_existing": True},
            ).status_code
            == 400
        )
        assert client.delete(url).status_code == 400
        assert client.delete(url + "?confirmed=true").status_code == 200
        assert (external / "b.py").exists()


def test_create_and_move_resources(tmp_path):
    """Empty folders persist and nested moves preserve content."""
    from cmf_dev_studio.projects.editor import create_directory, move_entry
    from cmf_dev_studio.projects.explorer import list_directory

    create_directory(tmp_path, "src")
    create_directory(tmp_path, "src/nested")
    create_directory(tmp_path, "tests")
    assert list_directory(tmp_path, "src")["entries"][0]["path"] == "src/nested"
    (tmp_path / "src/nested/a.py").write_text("hello")
    assert move_entry(tmp_path, "src/nested", "tests")["path"] == "tests/nested"
    assert move_entry(tmp_path, "tests/nested/a.py", "")["path"] == "a.py"
    assert (tmp_path / "a.py").read_text() == "hello"


def test_move_rejects_unsafe_destinations(tmp_path):
    """Collisions, descendants and symlinks cannot be used as destinations."""
    from cmf_dev_studio.projects.editor import create_directory, move_entry

    create_directory(tmp_path, "src")
    create_directory(tmp_path, "src/child")
    create_directory(tmp_path, "other")
    (tmp_path / "src/a").touch()
    (tmp_path / "other/a").touch()
    (tmp_path / "link").symlink_to(tmp_path / "other", target_is_directory=True)
    with pytest.raises(EditConflict):
        move_entry(tmp_path, "src/a", "other")
    for parent in ("src/child", "src", "../outside", "link"):
        with pytest.raises(ExplorerError):
            move_entry(tmp_path, "src", parent)
    with pytest.raises(ExplorerError):
        create_directory(tmp_path, ".git")
    assert (tmp_path / "src/a").exists()


def test_move_api_invalidates_pending_proposal(tmp_path):
    """A layout change prevents an already tested proposal from being applied."""
    from fastapi.testclient import TestClient

    from cmf_dev_studio.api.app import create_app
    from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService

    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("demo")
    (project.path / "a.py").touch()
    service = WorkspaceService(manager)
    pid = "a" * 32
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "tested", "task", "now"),
        )
    with TestClient(create_app(manager.data_dir)) as client:
        url = "/api/projects/" + project.id + "/editor"
        assert client.post(url + "/directory", json={"path": "src"}).status_code == 200
        assert (
            client.patch(
                url + "/move", json={"path": "a.py", "parent": "src"}
            ).status_code
            == 200
        )
    assert service.get(pid)["status"] == "failed"
    with pytest.raises(WorkspaceError):
        service.apply(pid, True)


def test_directory_and_move_require_external_authorization(tmp_path):
    """Registered projects require authorization for both new operations."""
    from fastapi.testclient import TestClient

    from cmf_dev_studio.api.app import create_app

    external = tmp_path / "repo"
    external.mkdir()
    (external / "a.py").touch()
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post(
            "/api/projects/register", json={"path": str(external)}
        ).json()
        url = "/api/projects/" + project["id"] + "/editor"
        assert client.post(url + "/directory", json={"path": "src"}).status_code == 403
        assert (
            client.post(
                url + "/directory", json={"path": "src", "authorize_existing": True}
            ).status_code
            == 200
        )
        assert (
            client.patch(
                url + "/move", json={"path": "a.py", "parent": "src"}
            ).status_code
            == 403
        )
        assert (
            client.patch(
                url + "/move",
                json={"path": "a.py", "parent": "src", "authorize_existing": True},
            ).status_code
            == 200
        )


def test_batch_move_and_delete(tmp_path):
    """Nested selections are processed once and files retain their contents."""
    from cmf_dev_studio.projects.editor import batch_entries

    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "dest").mkdir()
    result = batch_entries(tmp_path, ["src", "src/a.py", "b.py"], "dest")
    assert len(result["completed"]) == 2 and result["error"] is None
    assert (tmp_path / "dest/src/a.py").read_text() == "a"
    assert (tmp_path / "dest/b.py").read_text() == "b"
    result = batch_entries(tmp_path, ["dest/src", "dest/src/a.py", "dest/b.py"], None)
    assert len(result["completed"]) == 2 and not list((tmp_path / "dest").iterdir())


def test_batch_conflict_preflight(tmp_path):
    """A collision prevents any move in the batch."""
    from cmf_dev_studio.projects.editor import batch_entries

    (tmp_path / "dest").mkdir()
    for name in ["a.py", "b.py", "dest/b.py"]:
        (tmp_path / name).write_text(name)
    with pytest.raises(EditConflict):
        batch_entries(tmp_path, ["a.py", "b.py"], "dest")
    assert (tmp_path / "a.py").exists() and (tmp_path / "b.py").exists()


def test_batch_invalid_descendant(tmp_path):
    """A folder cannot be moved into a descendant, even in a batch."""
    from cmf_dev_studio.projects.editor import batch_entries

    (tmp_path / "src/sub").mkdir(parents=True)
    (tmp_path / "a.py").touch()
    with pytest.raises(ExplorerError):
        batch_entries(tmp_path, ["a.py", "src"], "src/sub")
    assert (tmp_path / "a.py").exists()


def test_batch_api_confirmation_and_authorization(tmp_path):
    """Batch deletion requires both explicit confirmation and external authorization."""
    from fastapi.testclient import TestClient

    from cmf_dev_studio.api.app import create_app

    external = tmp_path / "repo"
    external.mkdir()
    for name in ("a.py", "b.py"):
        (external / name).touch()
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post(
            "/api/projects/register", json={"path": str(external)}
        ).json()
        url = "/api/projects/" + project["id"] + "/editor/batch"
        payload = {"paths": ["a.py", "b.py"], "parent": None}
        assert client.post(url, json={**payload, "confirmed": True}).status_code == 403
        assert (
            client.post(url, json={**payload, "authorize_existing": True}).status_code
            == 400
        )
        assert len(list(external.iterdir())) == 2
        response = client.post(
            url, json={**payload, "confirmed": True, "authorize_existing": True}
        )
        assert response.status_code == 200
        assert len(response.json()["completed"]) == 2
        assert not list(external.iterdir())


def test_copy_entries(tmp_path):
    """Copy nested selections once, preserve originals and duplicate safely."""
    from cmf_dev_studio.projects.editor import copy_entries

    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("hello")
    (tmp_path / "dest").mkdir()
    result = copy_entries(tmp_path, ["src", "src/a.py"], "dest")
    assert result["error"] is None and len(result["completed"]) == 1
    assert (tmp_path / "dest/src/a.py").read_text() == "hello"
    assert (tmp_path / "src/a.py").read_text() == "hello"
    assert copy_entries(tmp_path, ["src/a.py"], "src")["error"] is None
    assert (tmp_path / "src/a (1).py").read_text() == "hello"


def test_copy_conflicts_and_links(tmp_path):
    """Number collisions and reject descendant destinations and symbolic links."""
    from cmf_dev_studio.projects.editor import copy_entries

    (tmp_path / "src/sub").mkdir(parents=True)
    (tmp_path / "dest").mkdir()
    (tmp_path / "a.py").touch()
    (tmp_path / "dest/a.py").touch()
    result = copy_entries(tmp_path, ["src", "a.py"], "dest")
    assert result["error"] is None
    assert (tmp_path / "dest/src").is_dir()
    assert (tmp_path / "dest/a (1).py").is_file()
    assert (tmp_path / "dest/a.py").is_file()
    with pytest.raises(ExplorerError):
        copy_entries(tmp_path, ["src"], "src/sub")
    (tmp_path / "src/link").symlink_to(tmp_path / "a.py")
    with pytest.raises(ExplorerError):
        copy_entries(tmp_path, ["src"], "dest")


def test_copy_api_authorization(tmp_path):
    """Registered projects require explicit write authorization for paste."""
    from fastapi.testclient import TestClient

    from cmf_dev_studio.api.app import create_app

    external = tmp_path / "repo"
    external.mkdir()
    (external / "a.py").write_text("a")
    with TestClient(create_app(tmp_path / "studio")) as client:
        project = client.post(
            "/api/projects/register", json={"path": str(external)}
        ).json()
        url = "/api/projects/" + project["id"] + "/editor/copy"
        payload = {"paths": ["a.py"], "parent": ""}
        assert client.post(url, json=payload).status_code == 403
        assert (
            client.post(url, json={**payload, "authorize_existing": True}).status_code
            == 200
        )
        assert (external / "a (1).py").read_text() == "a"


def test_copy_numbered_conflicts(tmp_path):
    """Number repeated file and folder copies without overwriting existing entries."""
    from cmf_dev_studio.projects.editor import copy_entries

    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("source")
    (tmp_path / "dest").mkdir()
    (tmp_path / "dest/main.py").write_text("original")
    for number in (1, 2, 3):
        result = copy_entries(tmp_path, ["src/main.py"], "dest")
        assert result["error"] is None
        assert result["completed"][0]["path"] == f"dest/main ({number}).py"
        assert (tmp_path / f"dest/main ({number}).py").read_text() == "source"
    assert (tmp_path / "dest/main.py").read_text() == "original"
    for number in (1, 2):
        result = copy_entries(tmp_path, ["src"], "")
        assert result["error"] is None
        assert (tmp_path / f"src ({number})/main.py").read_text() == "source"


def test_copy_numbered_batch_collision(tmp_path):
    """Reserve distinct names for same-named files in a single paste."""
    from cmf_dev_studio.projects.editor import copy_entries

    for folder in ("a", "b", "dest"):
        (tmp_path / folder).mkdir()
    (tmp_path / "a/main.py").write_text("a")
    (tmp_path / "b/main.py").write_text("b")
    result = copy_entries(tmp_path, ["a/main.py", "b/main.py"], "dest")
    assert result["error"] is None
    assert (tmp_path / "dest/main.py").read_text() == "a"
    assert (tmp_path / "dest/main (1).py").read_text() == "b"
