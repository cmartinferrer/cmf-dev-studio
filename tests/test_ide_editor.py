from fastapi.testclient import TestClient
from cmf_dev_studio.api.app import create_app


def test_editor_save_conflict_and_create(tmp_path):
    client = TestClient(create_app(tmp_path / 'state'))
    project = client.post('/api/projects', json={'name': 'demo'}).json()
    pid = project['id']
    url = f'/api/projects/{pid}/editor/file'
    assert client.put(url, json={'path': 'app/main.py', 'content': 'hello', 'create': True}).status_code == 200
    current = client.get(url, params={'path': 'app/main.py'}).json()
    assert current['content'] == 'hello'
    assert client.put(url, json={'path': 'app/main.py', 'content': 'changed', 'expected_sha256': 'bad'}).status_code == 409
    assert client.put(url, json={'path': 'app/main.py', 'content': 'changed', 'expected_sha256': current['sha256']}).status_code == 200
    assert client.get(url, params={'path': 'app/main.py'}).json()['content'] == 'changed'
    assert client.put(url, json={'path': '../escape', 'content': 'bad', 'create': True}).status_code == 422
    assert client.put(url, json={'path': '.env', 'content': 'bad', 'create': True}).status_code == 422


def test_existing_requires_authorization_and_symlink_block(tmp_path):
    root = tmp_path / 'existing'; root.mkdir()
    (root / 'main.py').write_text('old')
    (root / 'link.py').symlink_to(tmp_path / 'elsewhere')
    client = TestClient(create_app(tmp_path / 'state'))
    pid = client.post('/api/projects/register', json={'path': str(root)}).json()['id']
    url = f'/api/projects/{pid}/editor/file'
    rev = client.get(url, params={'path': 'main.py'}).json()['sha256']
    payload = {'path': 'main.py', 'content': 'new', 'expected_sha256': rev}
    assert client.put(url, json=payload).status_code == 403
    assert client.put(url, json={**payload, 'authorize_existing': True}).status_code == 200
    assert (root / 'main.py').read_text() == 'new'
    assert client.put(url, json={'path': 'link.py', 'content': 'bad', 'create': True, 'authorize_existing': True}).status_code == 422
