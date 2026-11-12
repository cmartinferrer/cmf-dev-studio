from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from multi_agent_software_team.projects.intelligence import analyze_repository, prepare_context
from multi_agent_software_team.projects.explorer import ExplorerError
from multi_agent_software_team.api.app import create_app


def test_inventory_is_bounded_and_ignores_secrets(tmp_path: Path):
    (tmp_path / 'pyproject.toml').write_text('[project]\nname="example"')
    (tmp_path / 'main.py').write_text('print("hi")')
    (tmp_path / '.env').write_text('TOKEN=secret')
    (tmp_path / 'password.py').write_text('private')
    (tmp_path / 'secrets').mkdir()
    (tmp_path / 'secrets' / 'other.py').write_text('private')
    info = analyze_repository(tmp_path)
    assert info['technologies'] == ['Python / pyproject']
    assert [entry['path'] for entry in info['candidates']] == ['main.py', 'pyproject.toml']


def test_explicit_selection_and_secret_scanning(tmp_path: Path):
    (tmp_path / 'main.py').write_text('def add(a, b): return a+b')
    (tmp_path / 'token.py').write_text('safe')
    (tmp_path / 'bad.py').write_text('api_key = "abcdefgh123456"')
    assert prepare_context(tmp_path, ['main.py'])['files'][0]['path'] == 'main.py'
    with pytest.raises(ExplorerError):
        prepare_context(tmp_path, ['token.py'])
    with pytest.raises(ExplorerError):
        prepare_context(tmp_path, ['bad.py'])
    with pytest.raises(ExplorerError):
        prepare_context(tmp_path, ['../main.py'])
    with pytest.raises(ExplorerError):
        prepare_context(tmp_path, ['main.py'] * 2)


def test_symlink_cannot_be_selected(tmp_path: Path):
    (tmp_path / 'outside.py').write_text('safe')
    (tmp_path / 'link.py').symlink_to(tmp_path / 'outside.py')
    with pytest.raises(ExplorerError):
        prepare_context(tmp_path, ['link.py'])


def test_insights_api_and_preview(tmp_path: Path):
    root = tmp_path / 'repository'
    root.mkdir()
    (root / 'app.py').write_text('def main(): pass')
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    project = client.post('/api/projects/register', json={'path': str(root)}).json()
    project_id = project['id']
    result = client.get(f'/api/projects/{project_id}/insights')
    assert result.status_code == 200
    assert result.json()['candidates'][0]['path'] == 'app.py'
    preview = client.post(f'/api/projects/{project_id}/context/preview', json={'paths': ['app.py']})
    assert preview.status_code == 200
    assert preview.json()['total_bytes'] > 0
    assert client.post(f'/api/projects/{project_id}/context/preview', json={'paths': ['.env']}).status_code == 422


def test_digest_changes_when_file_changes(tmp_path: Path):
    file = tmp_path / 'main.py'
    file.write_text('x = 1')
    before = prepare_context(tmp_path, ['main.py'])['digest']
    file.write_text('x = 2')
    assert before != prepare_context(tmp_path, ['main.py'])['digest']


