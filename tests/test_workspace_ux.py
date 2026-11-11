from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from multi_agent_software_team.api.app import create_app
from multi_agent_software_team.projects.browser import FolderBrowserError, browse_directory
from multi_agent_software_team.projects.search import search_files


def test_folder_picker_is_restricted_to_configured_root(tmp_path, monkeypatch):
    root = tmp_path / 'allowed'
    root.mkdir()
    (root / 'project').mkdir()
    (root / '.private').mkdir()
    monkeypatch.setenv('STUDIO_BROWSE_ROOT', str(root))
    result = browse_directory()
    assert result['path'] == str(root)
    assert [p['name'] for p in result['directories']] == ['project']
    assert browse_directory(str(root / 'project'))['parent'] == str(root)
    with pytest.raises(FolderBrowserError):
        browse_directory(str(tmp_path))
    with pytest.raises(FolderBrowserError):
        browse_directory(str(root / '.private'))


def test_folder_picker_rejects_symlinks(tmp_path, monkeypatch):
    root = tmp_path / 'allowed'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'link').symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv('STUDIO_BROWSE_ROOT', str(root))
    assert browse_directory()['directories'] == []
    with pytest.raises(FolderBrowserError):
        browse_directory(str(root / 'link'))


def test_filename_search_ignores_hidden_and_dependencies(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'main.py').write_text('hello')
    (tmp_path / '.env').write_text('secret')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'main.js').write_text('hidden')
    assert [p['path'] for p in search_files(tmp_path, 'main')['entries']] == ['src/main.py']
    assert search_files(tmp_path, 'env')['entries'] == []


def test_workspace_ux_endpoints(tmp_path, monkeypatch):
    root = tmp_path / 'projects'
    root.mkdir()
    (root / 'demo').mkdir()
    (root / 'demo' / 'hello.py').write_text('print(1)')
    monkeypatch.setenv('STUDIO_BROWSE_ROOT', str(root))
    client = TestClient(create_app(tmp_path / 'data'))
    listing = client.get('/api/local/directories')
    assert listing.status_code == 200
    assert listing.json()['directories'][0]['name'] == 'demo'
    assert client.get('/api/local/directories', params={'path': str(tmp_path)}).status_code == 400
    project = client.post('/api/projects/register', json={'path': str(root / 'demo')}).json()
    result = client.get(f"/api/projects/{project['id']}/search", params={'q': 'hello'})
    assert result.status_code == 200
    assert result.json()['entries'][0]['path'] == 'hello.py'
    assert client.get(f"/api/projects/{project['id']}/search", params={'q': ''}).status_code == 400
