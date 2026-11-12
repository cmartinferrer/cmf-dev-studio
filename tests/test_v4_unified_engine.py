"""V4 regression contracts: no language-specific agent restrictions or split engines."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent as QAAgent
from multi_agent_software_team.models import Mission
from multi_agent_software_team.project_runners import select_runner, UnsupportedRunner
from multi_agent_software_team.unified_engine import UnifiedEngine
from multi_agent_software_team.workspaces import validate_operations, WorkspaceError


@pytest.mark.parametrize('language,framework', [('Python', 'pytest'), ('Java', 'JUnit 5'), ('Kotlin', 'JUnit 5')])
def test_agents_follow_requested_language(language, framework):
    llm = Mock()
    llm.generate.return_value = 'sample code'
    mission = Mission(description='Implement feature', language=language)
    mission.requirements = ['Return a concrete result']
    DeveloperAgent(llm).execute(mission)
    developer_prompt = llm.generate.call_args.args[0]
    assert language in developer_prompt
    assert 'Return only valid Python source code' not in developer_prompt
    QAAgent(llm).execute(mission)
    tester_prompt = llm.generate.call_args.args[0]
    assert language in tester_prompt
    assert framework in tester_prompt
    assert 'experienced Python QA engineer' not in tester_prompt
    assert 'externally observable' in tester_prompt


def test_unified_engine_roles_and_permission_validation():
    responses = [
        json.dumps({'requirements': ['GET /version returns 0.1.0'], 'acceptance': ['GET /version returns a literal version string']}),
        json.dumps({'operations': [{'action': 'modify', 'path': 'src/Main.java', 'content': 'class Main {}'}]}),
        json.dumps({'issues': []}),
    ]
    llm = Mock()
    llm.generate.side_effect = responses
    engine = UnifiedEngine(llm)
    plan = engine.plan_patch('Add version endpoint', 'src/Main.java', 'FILE: src/Main.java\nclass Main {}', ['Java'])
    original = {'src/Main.java': b'class Main {}'}
    operations = engine.generate_patch('Return JSON operations', plan,
        validate=lambda ops: validate_operations(ops, original, {'src/Main.java'}))
    assert not engine.review_patch('Add version endpoint', plan, operations)
    assert llm.generate.call_count == 3
    assert 'ROLE: ANALYST' in llm.generate.call_args_list[0].args[0]
    assert 'ROLE: DEVELOPER' in llm.generate.call_args_list[1].args[0]
    assert 'ROLE: TESTER' in llm.generate.call_args_list[2].args[0]
    with pytest.raises(WorkspaceError, match='Permission required'):
        validate_operations(operations, original, set())


@pytest.mark.parametrize('manifest,expected', [
    ('pom.xml', 'maven'), ('build.gradle.kts', 'gradle'),
    ('build.gradle', 'gradle'), ('app.py', 'pytest'),
])
def test_runner_selection_by_build_manifest(tmp_path, manifest, expected):
    (tmp_path / manifest).write_text('sample')
    if expected in ('maven', 'gradle'):
        (tmp_path / 'src/test/java').mkdir(parents=True)
        (tmp_path / 'src/test/java/AppTest.java').write_text('class AppTest {}')
    assert select_runner(tmp_path).name == expected


def test_runner_rejects_unsupported_project(tmp_path):
    (tmp_path / 'README.md').write_text('sample')
    with pytest.raises(UnsupportedRunner):
        select_runner(tmp_path)

@pytest.mark.parametrize('manifest,source_path', [
    ('pom.xml', 'src/main/java/demo/App.java'),
    ('build.gradle.kts', 'src/main/kotlin/demo/App.kt'),
])
def test_end_to_end_project_patch_review_test_apply_with_mocked_container(tmp_path, monkeypatch, manifest, source_path):
    """API -> roles -> safe snapshot -> selected runner -> explicit apply."""
    from fastapi.testclient import TestClient
    from multi_agent_software_team.api.app import create_app
    import multi_agent_software_team.workspaces as workspaces
    import sys, types, time
    from unittest.mock import patch

    project_root = tmp_path / 'project'
    project_root.mkdir()
    (project_root / manifest).write_text('build configuration')
    file = project_root / source_path
    file.parent.mkdir(parents=True)
    file.write_text('original source')
    test_source = project_root / ('src/test/java/demo/AppTest.java' if manifest == 'pom.xml' else 'src/test/kotlin/demo/AppTest.kt')
    test_source.parent.mkdir(parents=True)
    test_source.write_text('independent tests')
    client = TestClient(create_app(tmp_path / 'data'))
    project = client.post('/api/projects/register', json={'path': str(project_root)}).json()
    preview = client.post(f"/api/projects/{project['id']}/context/preview", json={'paths': [source_path]}).json()
    assert 'digest' in preview, preview

    responses = [
        json.dumps({'requirements': ['Expose a version'], 'acceptance': ['Returns version 0.1.0']}),
        json.dumps({'operations': [{'action': 'modify', 'path': source_path, 'content': 'revised source'}]}),
        json.dumps({'issues': []}),
    ]
    module = types.ModuleType('multi_agent_software_team.llm.gemini')
    class FakeGemini:
        def generate(self, prompt):
            return responses.pop(0)
    module.GeminiClient = FakeGemini
    with patch.dict(sys.modules, {'multi_agent_software_team.llm.gemini': module}):
        submitted = client.post(f"/api/projects/{project['id']}/proposals", json={
            'task': 'Add version', 'context_paths': [source_path], 'context_digest': preview['digest']})
        assert submitted.status_code == 202, submitted.text
        proposal_id = submitted.json()['id']
        for _ in range(100):
            result = client.get(f'/api/proposals/{proposal_id}').json()
            if result['status'] in ('ready', 'failed'):
                break
            time.sleep(.02)
    assert result['status'] == 'ready', result
    assert result['plan']['acceptance'] == ['Returns version 0.1.0']
    assert file.read_text() == 'original source'
    chosen = []
    def fake_runner(workspace, spec):
        chosen.append(spec.name)
        return True, 'Runner: ' + spec.name + ' (exit 0)\n1 test passed'
    monkeypatch.setattr(workspaces, 'execute_runner', fake_runner)
    tested = client.post(f'/api/proposals/{proposal_id}/test')
    assert tested.status_code == 200, tested.text
    assert tested.json()['status'] == 'tested'
    assert chosen == ['maven' if manifest == 'pom.xml' else 'gradle']
    assert file.read_text() == 'original source'
    applied = client.post(f'/api/proposals/{proposal_id}/apply', json={
        'confirmation': project['name'], 'allow_existing': True})
    assert applied.status_code == 200, applied.text
    assert file.read_text() == 'revised source'


def test_docker_runner_isolated_and_offline(tmp_path, monkeypatch):
    from multi_agent_software_team.project_runners import execute_runner, RunnerSpec
    import multi_agent_software_team.project_runners as runners
    recorded = {}
    def fake_run(command, **kwargs):
        recorded['command'] = command
        return type('Result', (), {'returncode': 0, 'stdout': '1 passed', 'stderr': ''})()
    monkeypatch.setattr(runners.subprocess, 'run', fake_run)
    passed, output = execute_runner(tmp_path, RunnerSpec('pytest', 'test-image', ('python', '-m', 'pytest')))
    assert passed and '1 passed' in output
    assert '--network' in recorded['command'] and 'none' in recorded['command']
    assert '--read-only' in recorded['command']
    assert 'readonly' in ' '.join(recorded['command'])
    assert recorded['command'][-3:] == ['python', '-m', 'pytest']


def test_tampered_workspace_cannot_be_applied(tmp_path, monkeypatch):
    from multi_agent_software_team.projects.manager import ProjectManager
    from multi_agent_software_team.workspaces import WorkspaceService, tree_digest
    manager = ProjectManager(tmp_path / 'data')
    project = manager.create('example')
    service = WorkspaceService(manager)
    proposal_id = 'c' * 32
    workspace = service.root / proposal_id
    workspace.mkdir()
    (workspace / 'main.py').write_text('original generated content')
    with service._db() as db:
        db.execute('INSERT INTO workspace_proposals(id,project_id,status,task,created_at,changes,tested_digest) VALUES (?,?,?,?,?,?,?)',
                   (proposal_id, project.id, 'tested', 'task', 'now', json.dumps([{
                       'action': 'create', 'path': 'main.py', 'before_sha256': None,
                       'size': 26, 'diff': ''}]), tree_digest(workspace)))
    (workspace / 'main.py').write_text('tampered after test')
    with pytest.raises(WorkspaceError, match='changed after testing'):
        service.apply(proposal_id, 'example')
    assert not (project.path / 'main.py').exists()
