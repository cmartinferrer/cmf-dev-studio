from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from multi_agent_software_team.api.app import create_app


@pytest.fixture
def workspace(tmp_path: Path):
    root = tmp_path / 'repository'
    root.mkdir()
    (root / 'hello.py').write_text('print("hello")\n')
    (root / 'nested').mkdir()
    (root / 'nested' / 'app.py').write_text('answer = 42\n')
    (root / '.env').write_text('SECRET=hidden')
    (root / '.git').mkdir()
    (root / '.git' / 'config').write_text('secret')
    (root / 'external').symlink_to(tmp_path, target_is_directory=True)
    client = TestClient(create_app(tmp_path / 'state'))
    response = client.post('/api/projects/register', json={'path': str(root)})
    assert response.status_code == 201, response.text
    return client, response.json()['id'], root


def test_list_and_preview(workspace):
    client, project_id, root = workspace
    response = client.get(f'/api/projects/{project_id}/files')
    assert response.status_code == 200
    assert [item['name'] for item in response.json()['entries']] == ['nested', 'hello.py']
    nested = client.get(f'/api/projects/{project_id}/files', params={'path': 'nested'})
    assert nested.json()['entries'][0]['path'] == 'nested/app.py'
    preview = client.get(f'/api/projects/{project_id}/file', params={'path': 'nested/app.py'})
    assert preview.json()['content'] == 'answer = 42\n'


@pytest.mark.parametrize('path', ['../other', '/etc/passwd', '.env', '.git/config', 'external', 'external/other'])
def test_reject_unsafe_paths(workspace, path):
    client, project_id, root = workspace
    assert client.get(f'/api/projects/{project_id}/files', params={'path': path}).status_code == 400
    assert client.get(f'/api/projects/{project_id}/file', params={'path': path}).status_code == 400


def test_reject_binary_and_large_files(workspace, tmp_path):
    client, project_id, root = workspace
    (root / 'binary.dat').write_bytes(b'abc\x00def')
    (root / 'huge.txt').write_bytes(b'x' * (256 * 1024 + 1))
    for filename in ('binary.dat', 'huge.txt'):
        assert client.get(f'/api/projects/{project_id}/file', params={'path': filename}).status_code == 400


def test_missing_project(workspace):
    client, _, root = workspace
    assert client.get('/api/projects/missing/files').status_code == 404
