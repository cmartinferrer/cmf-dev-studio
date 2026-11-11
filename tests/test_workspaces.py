import json
import time
from pathlib import Path
from unittest.mock import patch
import sys
import types

import pytest
from fastapi.testclient import TestClient
from multi_agent_software_team.api.app import create_app
from multi_agent_software_team.workspaces import WorkspaceError, safe_path, snapshot

@pytest.mark.parametrize('path', ['../secret.py', '/tmp/x.py', '.env', 'src/.hidden.py', 'src/../../x.py', 'src/a.exe', 'src\\a.py', 'src/.git/config', 'src/a.py:evil'])
def test_reject_unsafe_paths(path):
    with pytest.raises(WorkspaceError):
        safe_path(path)

def test_snapshot_skips_secrets_symlinks(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'main.py').write_text('x = 1')
    (source / '.env').write_text('SECRET=abc')
    (source / 'linked.py').symlink_to(source / 'main.py')
    target = tmp_path / 'target'; target.mkdir()
    result = snapshot(source, target)
    assert result == {'main.py': b'x = 1'}
    assert not (target / '.env').exists()
    assert not (target / 'linked.py').exists()

from contextlib import contextmanager

@contextmanager
def fake_gemini(response):
    module = types.ModuleType('multi_agent_software_team.llm.gemini')
    class GeminiClient:
        def generate(self, prompt): return response
    module.GeminiClient = GeminiClient
    with patch.dict(sys.modules, {'multi_agent_software_team.llm.gemini': module}):
        yield

def test_new_project_proposal_api(tmp_path):
    client = TestClient(create_app(tmp_path / 'data'))
    project = client.post('/api/projects', json={'name':'hello-fastapi'}).json()
    response = {'operations': [
        {'action':'create', 'path':'main.py', 'content':'from fastapi import FastAPI\napp = FastAPI()\n'},
        {'action':'create', 'path':'tests/test_main.py', 'content':'def test_ok(): assert True\n'},
    ]}
    with fake_gemini(json.dumps(response)):
        submitted = client.post(f"/api/projects/{project['id']}/proposals", json={'task':'Create a FastAPI app'})
        assert submitted.status_code == 202, submitted.text
        proposal_id = submitted.json()['id']
        for _ in range(100):
            proposal = client.get(f'/api/proposals/{proposal_id}').json()
            if proposal['status'] in ('ready', 'failed'): break
            time.sleep(.02)
    assert proposal['status'] == 'ready', proposal
    assert len(proposal['changes']) == 2
    assert '+from fastapi import FastAPI' in proposal['changes'][0]['diff']
    assert list(Path(project['path']).iterdir()) == []

def test_existing_project_proposal_preserves_original(tmp_path):
    client = TestClient(create_app(tmp_path / 'data'))
    source = tmp_path / 'source'; source.mkdir()
    (source / 'main.py').write_text('answer = 1\n')
    project = client.post('/api/projects/register', json={'path':str(source)}).json()
    preview = client.post(f"/api/projects/{project['id']}/context/preview", json={'paths':['main.py']}).json()
    result = {'operations':[{'action':'modify', 'path':'main.py', 'content':'answer = 2\n'}]}
    with fake_gemini(json.dumps(result)):
        submitted = client.post(f"/api/projects/{project['id']}/proposals", json={'task':'Update answer', 'context_paths':['main.py'], 'context_digest':preview['digest']})
        assert submitted.status_code == 202, submitted.text
        for _ in range(100):
            proposal = client.get('/api/proposals/'+submitted.json()['id']).json()
            if proposal['status'] in ('ready', 'failed'): break
            time.sleep(.02)
    assert proposal['status'] == 'ready', proposal
    assert '-answer = 1' in proposal['changes'][0]['diff']
    assert '+answer = 2' in proposal['changes'][0]['diff']
    assert (source/'main.py').read_text() == 'answer = 1\n'

def test_proposal_diff_preview_is_read_only_and_detects_conflicts(tmp_path):
    client = TestClient(create_app(tmp_path / 'data'))
    source = tmp_path / 'source'; source.mkdir()
    (source / 'main.py').write_text('answer = 1\n')
    project = client.post('/api/projects/register', json={'path': str(source)}).json()
    context = client.post(f"/api/projects/{project['id']}/context/preview", json={'paths': ['main.py']}).json()
    with fake_gemini(json.dumps({'operations': [{'action': 'modify', 'path': 'main.py', 'content': 'answer = 2\n'}]})):
        created = client.post(f"/api/projects/{project['id']}/proposals", json={
            'task': 'Update answer', 'context_paths': ['main.py'], 'context_digest': context['digest']
        }).json()
        for _ in range(100):
            proposal = client.get(f"/api/proposals/{created['id']}").json()
            if proposal['status'] in ('ready', 'failed'): break
            time.sleep(.02)
    assert proposal['status'] == 'ready'
    result = client.get(f"/api/proposals/{created['id']}/preview", params={'path': 'main.py'})
    assert result.status_code == 200, result.text
    assert result.json()['before'] == 'answer = 1\n'
    assert result.json()['after'] == 'answer = 2\n'
    assert (source / 'main.py').read_text() == 'answer = 1\n'
    assert client.get(f"/api/proposals/{created['id']}/preview", params={'path': '../secret.py'}).status_code == 409
    (source / 'main.py').write_text('answer = 99\n')
    assert client.get(f"/api/proposals/{created['id']}/preview", params={'path': 'main.py'}).status_code == 409
