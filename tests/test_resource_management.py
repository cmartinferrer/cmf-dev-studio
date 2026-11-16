"""Regression tests for explicit project and filesystem management."""
import pytest
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.editor import rename_entry, delete_entry, EditConflict
from cmf_dev_studio.projects.explorer import ExplorerError


def test_project_rename_preserves_identity_and_files(tmp_path):
    """Display names never relocate the project or its files."""
    manager = ProjectManager(tmp_path / 'studio')
    project = manager.create('Old')
    (project.path / 'main.py').write_text('hello')
    renamed = manager.rename(project.id, 'New')
    assert renamed.id == project.id and renamed.path == project.path
    assert ProjectManager(manager.data_dir).get(project.id).name == 'New'
    assert (project.path / 'main.py').read_text() == 'hello'


def test_delete_managed_and_unregister_external(tmp_path):
    """Only managed workspaces are removed from disk."""
    manager = ProjectManager(tmp_path / 'studio')
    managed = manager.create('Managed')
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'main.py').write_text('keep')
    registered = manager.register_existing(external)
    assert manager.delete(managed.id) and not managed.path.exists()
    assert manager.delete(registered.id) and (external / 'main.py').exists()
    assert manager.list_projects() == []


def test_rename_and_delete_folder(tmp_path):
    """Folder operations preserve nested content until explicitly deleted."""
    folder = tmp_path / 'src'
    folder.mkdir()
    (folder / 'a.py').write_text('hello')
    assert rename_entry(tmp_path, 'src/a.py', 'b.py')['path'] == 'src/b.py'
    assert rename_entry(tmp_path, 'src', 'code')['path'] == 'code'
    assert (tmp_path / 'code/b.py').read_text() == 'hello'
    assert delete_entry(tmp_path, 'code')['deleted']
    assert not (tmp_path / 'code').exists()


@pytest.mark.parametrize('name', ['../escape', '.git', 'a/b', 'a\\b', ''])
def test_invalid_names(tmp_path, name):
    """Names cannot escape the parent or target protected entries."""
    (tmp_path / 'a').touch()
    with pytest.raises(ExplorerError):
        rename_entry(tmp_path, 'a', name)


def test_collision_and_symlink(tmp_path):
    """Existing targets and symbolic links cannot be overwritten or followed."""
    (tmp_path / 'a').touch()
    (tmp_path / 'b').touch()
    (tmp_path / 'link').symlink_to(tmp_path / 'b')
    with pytest.raises(EditConflict):
        rename_entry(tmp_path, 'a', 'b')
    with pytest.raises(ExplorerError):
        delete_entry(tmp_path, 'link')
    assert (tmp_path / 'b').exists()


def test_api_resource_permissions(tmp_path):
    """External writes and destructive actions require explicit authorization."""
    from fastapi.testclient import TestClient
    from cmf_dev_studio.api.app import create_app
    external = tmp_path / 'repo'
    external.mkdir()
    (external / 'a.py').touch()
    with TestClient(create_app(tmp_path / 'studio')) as client:
        project = client.post('/api/projects/register', json={'path': str(external)}).json()
        url = '/api/projects/' + project['id']
        assert client.patch(url+'/name', json={'name':'Renamed'}).status_code == 200
        assert client.patch(url+'/editor/entry', json={'path':'a.py','name':'b.py'}).status_code == 403
        assert client.patch(url+'/editor/entry', json={'path':'a.py','name':'b.py','authorize_existing':True}).status_code == 200
        assert client.request('DELETE',url+'/editor/entry',json={'path':'b.py','authorize_existing':True}).status_code == 400
        assert client.delete(url).status_code == 400
        assert client.delete(url+'?confirmed=true').status_code == 200
        assert (external/'b.py').exists()
